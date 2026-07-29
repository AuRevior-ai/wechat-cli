import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wechat_cli.core.asr import (
    Asset,
    AsrInstallError,
    MODEL_ASSET,
    RUNTIME_ASSET,
    OfflineAsrManager,
    parse_asr_stdout,
    safe_extract_tar_bz2,
)


def _tar_bz2(path, members):
    with tarfile.open(path, "w:bz2") as archive:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


class OfflineAsrInstallTests(unittest.TestCase):
    def test_assets_are_pinned_to_https_and_sha256(self):
        for asset in (RUNTIME_ASSET, MODEL_ASSET):
            self.assertTrue(asset.url.startswith("https://"))
            self.assertRegex(asset.sha256, r"^[0-9a-f]{64}$")
            self.assertGreater(asset.max_bytes, 0)

    def test_rejects_download_with_wrong_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            asset = Asset(
                name="bad",
                url="https://example.invalid/bad.tar.bz2",
                sha256="0" * 64,
                filename="bad.tar.bz2",
                max_bytes=1024,
            )
            manager = OfflineAsrManager(
                cache_dir=tmp,
                downloader=lambda _asset, _target, _progress: b"tampered",
            )

            with self.assertRaisesRegex(AsrInstallError, "SHA-256"):
                manager.ensure_archive(asset)

    def test_accepts_verified_download_and_reuses_cache(self):
        payload = b"verified archive"
        digest = hashlib.sha256(payload).hexdigest()
        calls = []

        def downloader(_asset, _target, _progress):
            calls.append(True)
            return payload

        with tempfile.TemporaryDirectory() as tmp:
            asset = Asset(
                name="good",
                url="https://example.invalid/good.tar.bz2",
                sha256=digest,
                filename="good.tar.bz2",
                max_bytes=1024,
            )
            manager = OfflineAsrManager(cache_dir=tmp, downloader=downloader)

            first = manager.ensure_archive(asset)
            second = manager.ensure_archive(asset)

            self.assertEqual(first, second)
            self.assertEqual(first.read_bytes(), payload)
            self.assertEqual(len(calls), 1)

    def test_safe_extract_rejects_parent_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = _tar_bz2(Path(tmp) / "bad.tar.bz2", [
                ("../escape.dll", b"bad"),
            ])

            with self.assertRaisesRegex(AsrInstallError, "非法路径"):
                safe_extract_tar_bz2(archive, Path(tmp) / "runtime")

    def test_safe_extract_rejects_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "link.tar.bz2"
            with tarfile.open(archive, "w:bz2") as output:
                info = tarfile.TarInfo("runtime/link.dll")
                info.type = tarfile.SYMTYPE
                info.linkname = "../outside.dll"
                output.addfile(info)

            with self.assertRaisesRegex(AsrInstallError, "链接"):
                safe_extract_tar_bz2(archive, Path(tmp) / "runtime")

    def test_safe_extract_writes_regular_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = _tar_bz2(Path(tmp) / "good.tar.bz2", [
                ("runtime/bin/tool.exe", b"exe"),
            ])
            destination = Path(tmp) / "output"

            safe_extract_tar_bz2(archive, destination)

            self.assertEqual(
                (destination / "runtime" / "bin" / "tool.exe").read_bytes(),
                b"exe",
            )

    def test_component_cache_names_stay_short_on_windows(self):
        manager = OfflineAsrManager(cache_dir="cache")

        runtime = manager.component_destination(
            RUNTIME_ASSET, "sherpa-onnx-offline.exe"
        )
        model = manager.component_destination(MODEL_ASSET, "model.int8.onnx")

        self.assertRegex(runtime.name, r"^runtime-[0-9a-f]{12}$")
        self.assertRegex(model.name, r"^model-[0-9a-f]{12}$")
        self.assertLessEqual(len(runtime.name), 20)
        self.assertLessEqual(len(model.name), 20)


class OfflineAsrRecognitionTests(unittest.TestCase):
    def test_parse_asr_stdout_finds_json_result(self):
        text = 'diagnostic\n{"lang":"","text":"今天没有困惑","tokens":[]}\nDone'

        self.assertEqual(parse_asr_stdout(text), "今天没有困惑")

    def test_parse_asr_stdout_rejects_missing_result(self):
        with self.assertRaisesRegex(RuntimeError, "识别结果"):
            parse_asr_stdout("diagnostic only")

    def test_transcript_cache_uses_audio_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wav = root / "voice.wav"
            wav.write_bytes(b"RIFF voice bytes")
            runtime = root / "runtime" / "bin" / "sherpa-onnx-offline.exe"
            runtime.parent.mkdir(parents=True)
            runtime.write_bytes(b"exe")
            model = root / "model"
            model.mkdir()
            (model / "tokens.txt").write_text("tokens", encoding="utf-8")
            (model / "model.int8.onnx").write_bytes(b"model")
            runner = mock.Mock(return_value=mock.Mock(
                stdout='{"text":"缓存内容"}\n',
                stderr="",
                returncode=0,
            ))
            manager = OfflineAsrManager(cache_dir=root / "cache", runner=runner)
            manager.ensure_ready = mock.Mock(return_value=(runtime.parent, model))

            first = manager.transcribe(wav)
            second = manager.transcribe(wav)

            self.assertEqual(first, "缓存内容")
            self.assertEqual(second, "缓存内容")
            self.assertEqual(runner.call_count, 1)
            cache_files = list((root / "cache" / "transcripts").glob("*.json"))
            self.assertEqual(len(cache_files), 1)
            cached = json.loads(cache_files[0].read_text(encoding="utf-8"))
            self.assertEqual(cached["text"], "缓存内容")


if __name__ == "__main__":
    unittest.main()
