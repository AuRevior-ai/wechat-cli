"""经过固定哈希校验的本地离线语音识别。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from threading import RLock
from typing import Callable
from urllib.request import Request, urlopen

from .config import STATE_DIR


_MIB = 1024 * 1024
_MAX_EXTRACTED_BYTES = 512 * _MIB
_MAX_ARCHIVE_MEMBERS = 10000


class AsrInstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    sha256: str
    filename: str
    max_bytes: int


RUNTIME_ASSET = Asset(
    name="sherpa-onnx-runtime-1.13.4-win-x64",
    url=(
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.4/"
        "sherpa-onnx-v1.13.4-win-x64-shared-MT-Release-no-tts.tar.bz2"
    ),
    sha256="e33dc64195d17601879532583233d0d6ed76aa399eb863e5ca0783c5ac82b5aa",
    filename="sherpa-onnx-v1.13.4-win-x64.tar.bz2",
    max_bytes=32 * _MIB,
)
MODEL_ASSET = Asset(
    name="sherpa-onnx-paraformer-zh-small-2024-03-09",
    url=(
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
        "sherpa-onnx-paraformer-zh-small-2024-03-09.tar.bz2"
    ),
    sha256="da92b3db5218c5be53aad53e57d1b6e63e7fc98a0e054fbdd6dbe18e9c6b1450",
    filename="sherpa-onnx-paraformer-zh-small-2024-03-09.tar.bz2",
    max_bytes=96 * _MIB,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_MIB), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_member_path(destination: Path, member_name: str) -> Path:
    if not member_name or "\\" in member_name or re.match(r"^[A-Za-z]:", member_name):
        raise AsrInstallError(f"压缩包包含非法路径: {member_name!r}")
    relative = PurePosixPath(member_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise AsrInstallError(f"压缩包包含非法路径: {member_name!r}")
    target = destination.joinpath(*relative.parts)
    destination_resolved = destination.resolve()
    target_resolved = target.resolve()
    try:
        target_resolved.relative_to(destination_resolved)
    except ValueError as exc:
        raise AsrInstallError(f"压缩包包含非法路径: {member_name!r}") from exc
    return target


def safe_extract_tar_bz2(
    archive_path: str | os.PathLike[str],
    destination: str | os.PathLike[str],
) -> Path:
    """只解压普通文件和目录，并阻止路径穿越、链接与解压炸弹。"""
    target_root = Path(destination)
    target_root.mkdir(parents=True, exist_ok=True)
    try:
        archive = tarfile.open(archive_path, "r:bz2")
    except (OSError, tarfile.TarError) as exc:
        raise AsrInstallError(f"无法读取语音组件压缩包: {exc}") from exc
    with archive:
        members = archive.getmembers()
        if len(members) > _MAX_ARCHIVE_MEMBERS:
            raise AsrInstallError("语音组件压缩包文件数量异常")
        total_size = 0
        validated = []
        for member in members:
            path = _validated_member_path(target_root, member.name)
            if member.issym() or member.islnk():
                raise AsrInstallError(f"语音组件压缩包不允许链接: {member.name}")
            if not (member.isdir() or member.isfile()):
                raise AsrInstallError(f"语音组件压缩包包含不支持的条目: {member.name}")
            total_size += int(member.size or 0)
            if total_size > _MAX_EXTRACTED_BYTES:
                raise AsrInstallError("语音组件解压后体积异常")
            validated.append((member, path))

        for member, path in validated:
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise AsrInstallError(f"无法读取压缩包条目: {member.name}")
            with source, path.open("wb") as output:
                shutil.copyfileobj(source, output, length=_MIB)
            if member.mode:
                try:
                    path.chmod(member.mode & 0o777)
                except OSError:
                    pass
    return target_root


def parse_asr_stdout(stdout: str) -> str:
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = payload.get("text") if isinstance(payload, dict) else None
        if isinstance(text, str) and text.strip():
            return text.strip()
    raise RuntimeError("离线模型没有返回可用的识别结果")


class OfflineAsrManager:
    def __init__(
        self,
        cache_dir: str | os.PathLike[str] | None = None,
        *,
        downloader: Callable | None = None,
        runner: Callable | None = None,
        progress: Callable[[str], None] | None = None,
    ):
        self.cache_dir = Path(cache_dir or (Path(STATE_DIR) / "models" / "offline-asr"))
        self.downloader = downloader
        self.runner = runner or subprocess.run
        self.progress = progress or (lambda _message: None)
        self._lock = RLock()

    @property
    def downloads_dir(self) -> Path:
        return self.cache_dir / "downloads"

    @property
    def components_dir(self) -> Path:
        return self.cache_dir / "components"

    @property
    def transcripts_dir(self) -> Path:
        return self.cache_dir / "transcripts"

    def _default_download(self, asset: Asset, target: Path) -> None:
        request = Request(asset.url, headers={"User-Agent": "wechat-cli/0.4"})
        total = 0
        try:
            response = urlopen(request, timeout=60)
            with response, target.open("wb") as output:
                while True:
                    chunk = response.read(_MIB)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > asset.max_bytes:
                        raise AsrInstallError(f"{asset.name} 下载体积超过安全限制")
                    output.write(chunk)
                    self.progress(
                        f"正在下载{asset.name}：{total / _MIB:.1f} MiB"
                    )
        except AsrInstallError:
            raise
        except Exception as exc:
            raise AsrInstallError(f"下载{asset.name}失败: {exc}") from exc

    def ensure_archive(self, asset: Asset) -> Path:
        if not asset.url.startswith("https://") or not re.fullmatch(r"[0-9a-f]{64}", asset.sha256):
            raise AsrInstallError(f"{asset.name} 的下载配置不安全")
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        target = self.downloads_dir / asset.filename
        if target.is_file() and _sha256_file(target) == asset.sha256:
            return target

        part = target.with_name(target.name + ".part")
        try:
            if part.exists():
                part.unlink()
            self.progress(f"准备下载{asset.name}")
            if self.downloader is None:
                self._default_download(asset, part)
            else:
                result = self.downloader(asset, part, self.progress)
                if isinstance(result, (bytes, bytearray)):
                    part.write_bytes(bytes(result))
            if not part.is_file():
                raise AsrInstallError(f"{asset.name} 下载器没有生成文件")
            if part.stat().st_size > asset.max_bytes:
                raise AsrInstallError(f"{asset.name} 下载体积超过安全限制")
            actual = _sha256_file(part)
            if actual != asset.sha256:
                raise AsrInstallError(
                    f"{asset.name} SHA-256 校验失败（期望 {asset.sha256}，实际 {actual}）"
                )
            os.replace(part, target)
            return target
        finally:
            if part.exists():
                try:
                    part.unlink()
                except OSError:
                    pass

    def _ensure_component(
        self,
        asset: Asset,
        required_filename: str,
    ) -> Path:
        destination = self.component_destination(asset, required_filename)
        found = next(destination.rglob(required_filename), None) if destination.is_dir() else None
        if found is not None:
            return found.parent

        archive = self.ensure_archive(asset)
        self.components_dir.mkdir(parents=True, exist_ok=True)
        prefix = "rt" if required_filename.endswith(".exe") else "md"
        staging = self.components_dir / f".{prefix}-{uuid.uuid4().hex[:8]}.tmp"
        try:
            safe_extract_tar_bz2(archive, staging)
            required = next(staging.rglob(required_filename), None)
            if required is None:
                raise AsrInstallError(
                    f"{asset.name} 解压后缺少 {required_filename}"
                )
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(staging, destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
        found = next(destination.rglob(required_filename), None)
        if found is None:
            raise AsrInstallError(f"{asset.name} 安装不完整")
        return found.parent

    def component_destination(
        self,
        asset: Asset,
        required_filename: str,
    ) -> Path:
        prefix = "runtime" if required_filename.endswith(".exe") else "model"
        return self.components_dir / f"{prefix}-{asset.sha256[:12]}"

    def ensure_ready(self) -> tuple[Path, Path]:
        with self._lock:
            self.progress("正在准备离线语音识别组件")
            runtime_bin = self._ensure_component(
                RUNTIME_ASSET, "sherpa-onnx-offline.exe"
            )
            model_dir = self._ensure_component(MODEL_ASSET, "model.int8.onnx")
            if not (model_dir / "tokens.txt").is_file():
                raise AsrInstallError("离线语音模型缺少 tokens.txt")
            return runtime_bin, model_dir

    def _cache_path(self, audio_hash: str) -> Path:
        return self.transcripts_dir / f"{audio_hash}.json"

    def _read_cached(self, audio_hash: str) -> str | None:
        path = self._cache_path(audio_hash)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        text = payload.get("text") if isinstance(payload, dict) else None
        return text if isinstance(text, str) and text.strip() else None

    def _write_cached(self, audio_hash: str, text: str) -> None:
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        target = self._cache_path(audio_hash)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(
            json.dumps(
                {"audio_sha256": audio_hash, "text": text},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, target)

    def transcribe(self, wav_path: str | os.PathLike[str]) -> str:
        path = Path(wav_path)
        if not path.is_file():
            raise FileNotFoundError(f"找不到待识别音频: {path}")
        audio_hash = _sha256_file(path)
        with self._lock:
            cached = self._read_cached(audio_hash)
            if cached is not None:
                return cached
            runtime_bin, model_dir = self.ensure_ready()
            executable = runtime_bin / "sherpa-onnx-offline.exe"
            self.progress(f"正在离线转写语音: {path.name}")
            kwargs = {
                "cwd": str(runtime_bin),
                "capture_output": True,
                "stdin": subprocess.DEVNULL,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "timeout": 600,
                "env": {
                    **os.environ,
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                },
            }
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = self.runner(
                [
                    str(executable),
                    f"--tokens={model_dir / 'tokens.txt'}",
                    f"--paraformer={model_dir / 'model.int8.onnx'}",
                    "--num-threads=2",
                    str(path),
                ],
                **kwargs,
            )
            if int(getattr(proc, "returncode", 1)) != 0:
                stderr = (getattr(proc, "stderr", "") or "").strip()
                raise RuntimeError(f"离线语音识别失败: {stderr or '未知错误'}")
            text = parse_asr_stdout(getattr(proc, "stdout", "") or "")
            self._write_cached(audio_hash, text)
            return text
