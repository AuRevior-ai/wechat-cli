"""Resumable authenticated update download with no ticket in the URL."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .crypto import verify_file_sha256
from .errors import ErrorCode, UpdateError
from .state import atomic_write_json, read_json_object
from .versioning import SemanticVersion
from ..version import APP_VERSION


class DownloadResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    def __enter__(self) -> "DownloadResponse": ...

    def __exit__(self, *args: Any) -> bool | None: ...

    def read(self, size: int = -1) -> bytes: ...


DownloadOpener = Callable[[str, Mapping[str, str], float], DownloadResponse]


def _default_opener(
    url: str,
    headers: Mapping[str, str],
    timeout: float,
) -> DownloadResponse:
    return urlopen(Request(url, headers=dict(headers), method="GET"), timeout=timeout)


@dataclass(frozen=True)
class DownloadRequest:
    download_url: str
    download_ticket: str = field(repr=False)
    release_id: str
    version: str
    filename: str
    expected_size: int
    expected_sha256: str

    def __post_init__(self) -> None:
        parsed = urlparse(self.download_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("download_url must be an absolute HTTPS URL")
        if parsed.query or parsed.fragment or "ticket" in self.download_url.lower():
            raise ValueError("download ticket must not appear in the download URL")
        if not self.download_ticket:
            raise ValueError("download_ticket is required")
        if not self.release_id:
            raise ValueError("release_id is required")
        SemanticVersion.parse(self.version)
        if not self.filename or Path(self.filename).name != self.filename:
            raise ValueError("filename must be a base filename")
        if self.expected_size <= 0:
            raise ValueError("expected_size must be positive")
        if len(self.expected_sha256) != 64:
            raise ValueError("expected_sha256 must contain 64 hexadecimal characters")
        int(self.expected_sha256, 16)

    def identity(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "release_id": self.release_id,
            "version": self.version,
            "filename": self.filename,
            "expected_size": self.expected_size,
            "expected_sha256": self.expected_sha256.lower(),
        }


@dataclass
class _DownloadState:
    request: DownloadRequest
    downloaded_bytes: int = 0
    etag: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            **self.request.identity(),
            "downloaded_bytes": self.downloaded_bytes,
            "etag": self.etag,
        }


def _state_matches(
    data: Mapping[str, Any],
    request: DownloadRequest,
    part_size: int,
) -> bool:
    identity = request.identity()
    for key, value in identity.items():
        if data.get(key) != value:
            return False
    downloaded = data.get("downloaded_bytes")
    if isinstance(downloaded, bool) or not isinstance(downloaded, int):
        return False
    if downloaded != part_size or downloaded < 0 or downloaded > request.expected_size:
        return False
    etag = data.get("etag")
    return etag is None or isinstance(etag, str)


def _remove_partial(part_path: Path, metadata_path: Path) -> None:
    for path in (part_path, metadata_path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _load_resume_state(
    request: DownloadRequest,
    part_path: Path,
    metadata_path: Path,
) -> _DownloadState:
    if not part_path.exists() or not metadata_path.exists():
        _remove_partial(part_path, metadata_path)
        return _DownloadState(request)
    try:
        data = read_json_object(metadata_path)
        size = part_path.stat().st_size
    except (OSError, UpdateError):
        _remove_partial(part_path, metadata_path)
        return _DownloadState(request)
    if not _state_matches(data, request, size):
        _remove_partial(part_path, metadata_path)
        return _DownloadState(request)
    return _DownloadState(
        request,
        downloaded_bytes=size,
        etag=data.get("etag"),
    )


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == target:
            return str(value)
    return None


def _validate_resumed_response(
    response: DownloadResponse,
    state: _DownloadState,
) -> tuple[int, str | None]:
    status = int(response.status)
    response_etag = _header(response.headers, "ETag")
    if state.downloaded_bytes == 0:
        if status != 200:
            raise OSError(f"update download returned HTTP {status}")
        return 0, response_etag
    if status == 200:
        return 0, response_etag
    if status != 206:
        raise OSError(f"update resume returned HTTP {status}")
    content_range = _header(response.headers, "Content-Range") or ""
    expected_prefix = f"bytes {state.downloaded_bytes}-"
    if not content_range.startswith(expected_prefix):
        raise OSError("update resume returned an invalid Content-Range")
    if state.etag is not None and response_etag is not None and state.etag != response_etag:
        raise OSError("update resume ETag changed unexpectedly")
    return state.downloaded_bytes, response_etag or state.etag


def download_update(
    request: DownloadRequest,
    download_dir: str | Path,
    *,
    opener: DownloadOpener = _default_opener,
    timeout_seconds: float = 30.0,
    chunk_size: int = 1024 * 1024,
) -> Path:
    if timeout_seconds <= 0 or chunk_size <= 0:
        raise ValueError("download timeout and chunk size must be positive")
    root = Path(download_dir)
    root.mkdir(parents=True, exist_ok=True)
    final_path = root / request.filename
    part_path = root / f"{request.filename}.part"
    metadata_path = root / f"{request.filename}.part.json"

    if final_path.exists():
        if final_path.stat().st_size == request.expected_size:
            try:
                verify_file_sha256(final_path, request.expected_sha256)
                return final_path
            except UpdateError:
                final_path.unlink()
        else:
            final_path.unlink()

    state = _load_resume_state(request, part_path, metadata_path)
    headers = {
        "Accept": "application/octet-stream",
        "Authorization": f"Download {request.download_ticket}",
        "User-Agent": f"WeChatCliUpdate/{APP_VERSION}",
    }
    if state.downloaded_bytes:
        headers["Range"] = f"bytes={state.downloaded_bytes}-"
        if state.etag:
            headers["If-Range"] = state.etag

    response = opener(request.download_url, headers, timeout_seconds)
    with response:
        offset, response_etag = _validate_resumed_response(response, state)
        if offset == 0 and part_path.exists():
            part_path.unlink()
        mode = "ab" if offset else "wb"
        state.downloaded_bytes = offset
        state.etag = response_etag
        atomic_write_json(metadata_path, state.to_mapping())
        with part_path.open(mode) as stream:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                stream.write(chunk)
                stream.flush()
                state.downloaded_bytes += len(chunk)
                atomic_write_json(metadata_path, state.to_mapping())
                if state.downloaded_bytes > request.expected_size:
                    _remove_partial(part_path, metadata_path)
                    raise UpdateError(
                        ErrorCode.UPDATE_HASH_MISMATCH,
                        "downloaded package exceeded its signed expected size",
                    )
            os.fsync(stream.fileno())

    if state.downloaded_bytes != request.expected_size:
        raise OSError(
            f"update download ended early: expected {request.expected_size}, got {state.downloaded_bytes}"
        )
    try:
        verify_file_sha256(part_path, request.expected_sha256)
    except UpdateError:
        _remove_partial(part_path, metadata_path)
        raise
    os.replace(part_path, final_path)
    try:
        metadata_path.unlink()
    except FileNotFoundError:
        pass
    return final_path
