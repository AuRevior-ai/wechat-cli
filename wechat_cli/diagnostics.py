"""Local, opt-in, redacted diagnostic bundle generation."""

from __future__ import annotations

import json
import os
import platform
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .update.layout import InstallLayout
from .version import APP_VERSION, BUILD_ID, LAUNCHER_VERSION, PRODUCT
from .windows.webview2 import detect_webview2_runtime

_LICENSE_PATTERN = re.compile(
    r"\bWCL(?:-[A-Za-z0-9]{4,}){3,}\b",
    re.IGNORECASE,
)
_DEVICE_TOKEN_PATTERN = re.compile(
    r"\bwcdt_[A-Za-z0-9_-]+\.[A-Za-z0-9._~-]+\b",
    re.IGNORECASE,
)
_ADMIN_TOKEN_PATTERN = re.compile(
    r"\bwcadmin_[A-Za-z0-9_-]+\.[A-Za-z0-9._~-]+\b",
    re.IGNORECASE,
)
_GITHUB_TOKEN_PATTERN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{12,}|github_pat_[A-Za-z0-9_]{8,})\b",
    re.IGNORECASE,
)
_AUTH_HEADER_PATTERN = re.compile(
    r"(?im)^(Authorization\s*:)(?![ \t]*\[REDACTED\][ \t]*\r?$)[ \t]*[^\r\n]+",
)
_COOKIE_HEADER_PATTERN = re.compile(
    r"(?im)^(Cookie\s*:)(?![ \t]*\[REDACTED\][ \t]*\r?$)[ \t]*[^\r\n]+",
)
_QUERY_SECRET_PATTERN = re.compile(
    r"(?i)([?&](?:ticket|token|key|secret|signature|authorization)=)(?!\[REDACTED\])([^&\s]+)",
)
_EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
_CONTACT_PATTERN = re.compile(
    r"(?i)\b(wechat|wxid|微信)\s*([:=])(?!\s*\[REDACTED\])\s*([^\s,;]+)",
)

_SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("authorization_header", _AUTH_HEADER_PATTERN),
    ("cookie_header", _COOKIE_HEADER_PATTERN),
    ("license_key", _LICENSE_PATTERN),
    ("device_token", _DEVICE_TOKEN_PATTERN),
    ("admin_token", _ADMIN_TOKEN_PATTERN),
    ("github_token", _GITHUB_TOKEN_PATTERN),
    ("query_secret", _QUERY_SECRET_PATTERN),
    ("email", _EMAIL_PATTERN),
    ("contact", _CONTACT_PATTERN),
)


def scan_for_sensitive_content(text: str) -> list[str]:
    """Return stable finding names for any unredacted sensitive pattern."""

    if not isinstance(text, str):
        raise TypeError("sensitive scanner input must be text")
    return [name for name, pattern in _SENSITIVE_PATTERNS if pattern.search(text)]


class Redactor:
    def __init__(self, *, windows_user_name: str | None = None) -> None:
        user_name = windows_user_name or os.environ.get("USERNAME") or ""
        self.windows_user_name = user_name.strip()
        self._user_path_pattern = (
            re.compile(
                rf"(?i)([A-Za-z]:\\+Users\\+){re.escape(self.windows_user_name)}(?=\\+|\b)"
            )
            if self.windows_user_name
            else None
        )

    def redact(self, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError("redactor input must be text")
        value = _AUTH_HEADER_PATTERN.sub(r"\1 [REDACTED]", text)
        value = _COOKIE_HEADER_PATTERN.sub(r"\1 [REDACTED]", value)
        value = _LICENSE_PATTERN.sub("WCL-****-****-****-[REDACTED]", value)
        value = _DEVICE_TOKEN_PATTERN.sub("wcdt_[REDACTED]", value)
        value = _ADMIN_TOKEN_PATTERN.sub("wcadmin_[REDACTED]", value)
        value = _GITHUB_TOKEN_PATTERN.sub("[REDACTED_GITHUB_TOKEN]", value)
        value = _QUERY_SECRET_PATTERN.sub(r"\1[REDACTED]", value)
        value = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
        value = _CONTACT_PATTERN.sub(r"\1\2[REDACTED]", value)
        if self._user_path_pattern is not None:
            value = self._user_path_pattern.sub(r"\1[USER]", value)
        return value


@dataclass(frozen=True)
class DiagnosticBundleResult:
    path: Path
    sensitive_findings: tuple[str, ...]
    submitted: bool = False


def _default_system_info() -> Mapping[str, str]:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "executable_frozen": str(bool(getattr(sys, "frozen", False))).lower(),
    }


def _default_webview2_version() -> str | None:
    runtime = detect_webview2_runtime()
    return runtime.version if runtime is not None else None


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("diagnostic clock must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class DiagnosticBundleBuilder:
    """Build a local text-only ZIP after two independent redaction checks."""

    def __init__(
        self,
        *,
        layout: InstallLayout,
        redactor: Redactor | None = None,
        windows_user_name: str | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        webview2_version_provider: Callable[[], str | None] = _default_webview2_version,
        system_info_provider: Callable[[], Mapping[str, Any]] = _default_system_info,
        max_log_bytes: int = 2 * 1024 * 1024,
        max_total_log_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        if max_log_bytes <= 0 or max_total_log_bytes <= 0:
            raise ValueError("diagnostic log limits must be positive")
        if max_log_bytes > max_total_log_bytes:
            raise ValueError("per-log limit cannot exceed total log limit")
        self.layout = layout
        self.redactor = redactor or Redactor(windows_user_name=windows_user_name)
        self.now = now
        self.webview2_version_provider = webview2_version_provider
        self.system_info_provider = system_info_provider
        self.max_log_bytes = max_log_bytes
        self.max_total_log_bytes = max_total_log_bytes

    def _log_candidates(self) -> list[Path]:
        if not self.layout.logs_dir.exists():
            return []
        candidates: list[Path] = []
        for path in self.layout.logs_dir.glob("*.log"):
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                path.resolve(strict=True).relative_to(
                    self.layout.logs_dir.resolve(strict=True)
                )
            except (OSError, ValueError):
                continue
            candidates.append(path)
        return sorted(candidates, key=lambda item: item.name.casefold())

    def _read_log_tail(self, path: Path, remaining_total: int) -> tuple[str, int]:
        allowed = min(self.max_log_bytes, remaining_total)
        if allowed <= 0:
            return "[TRUNCATED: total diagnostic log limit reached]\n", 0
        size = path.stat().st_size
        start = max(0, size - allowed)
        with path.open("rb") as stream:
            if start:
                stream.seek(start)
            raw = stream.read(allowed)
        text = raw.decode("utf-8", errors="replace")
        if start:
            marker = f"[TRUNCATED: omitted first {start} bytes]\n"
            marker_bytes = marker.encode("utf-8")
            if len(marker_bytes) + len(raw) > self.max_log_bytes:
                maximum = max(0, self.max_log_bytes - len(marker_bytes))
                raw = raw[-maximum:] if maximum else b""
                text = raw.decode("utf-8", errors="replace")
            text = marker + text
        return text, len(raw)

    def _metadata(self, generated_at: datetime) -> dict[str, Any]:
        try:
            current = self.layout.load_current()
            current_version = current.current_version
            previous_version = current.previous_version
            channel = current.channel
        except Exception:
            current_version = APP_VERSION
            previous_version = None
            channel = "unknown"
        system = dict(self.system_info_provider())
        # Restrict provider output to scalar values so metadata stays predictable.
        safe_system = {
            str(key): value
            for key, value in system.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
        return {
            "schema_version": 1,
            "generated_at": _format_timestamp(generated_at),
            "product": PRODUCT,
            "current_version": current_version,
            "previous_version": previous_version,
            "launcher_version": LAUNCHER_VERSION,
            "build_id": BUILD_ID,
            "channel": channel,
            "webview2_runtime": self.webview2_version_provider(),
            "system": safe_system,
        }

    def _contents_text(self, log_names: Iterable[str]) -> str:
        included = "\n".join(f"- logs/{name}" for name in log_names) or "- 未找到可用日志"
        return (
            "WeChat CLI Web 脱敏诊断包\n"
            "============================\n\n"
            "本诊断包包含：\n"
            "- 应用、启动器、Windows 与 WebView2 版本摘要\n"
            "- 启动、更新和回滚日志的脱敏副本\n\n"
            "本诊断包不会包含微信聊天记录、微信数据库、数据库密钥、"
            "完整许可证密钥、设备令牌、管理员或 GitHub Token、联系方式、"
            "MachineGuid 或 SID 原始值。\n\n"
            "实际包含的日志：\n"
            f"{included}\n"
        )

    def build_local(self) -> DiagnosticBundleResult:
        generated_at = self.now()
        if generated_at.tzinfo is None:
            raise ValueError("diagnostic clock must include a timezone")
        entries: dict[str, str] = {}
        remaining_total = self.max_total_log_bytes
        for path in self._log_candidates():
            text, consumed = self._read_log_tail(path, remaining_total)
            remaining_total = max(0, remaining_total - consumed)
            entries[f"logs/{path.name}"] = self.redactor.redact(text)

        metadata_text = json.dumps(
            self._metadata(generated_at),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n"
        entries["metadata.json"] = self.redactor.redact(metadata_text)
        log_names = [name.removeprefix("logs/") for name in entries if name.startswith("logs/")]
        entries["contents.txt"] = self._contents_text(log_names)

        findings: set[str] = set()
        for text in entries.values():
            findings.update(scan_for_sensitive_content(text))
        if findings:
            raise RuntimeError(
                "诊断包二次扫描发现未脱敏的敏感字段："
                + ", ".join(sorted(findings))
            )

        output_dir = self.layout.logs_dir / "diagnostics"
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = generated_at.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
        destination = output_dir / f"wechat-cli-diagnostics-{stamp}.zip"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=output_dir,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
            with zipfile.ZipFile(
                temporary,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as archive:
                for name, text in sorted(entries.items()):
                    archive.writestr(name, text.encode("utf-8"))
            os.replace(temporary, destination)
            temporary = None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
        return DiagnosticBundleResult(
            path=destination,
            sensitive_findings=tuple(sorted(findings)),
            submitted=False,
        )
