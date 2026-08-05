"""Safe inspection and extraction of signed application ZIP packages."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .errors import ErrorCode, UpdateError
from .versioning import SemanticVersion

_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class PackageLimits:
    max_entries: int = 10_000
    max_single_file_size: int = 512 * 1024 * 1024
    max_total_size: int = 1024 * 1024 * 1024
    max_compression_ratio: float = 200.0
    max_manifest_size: int = 1024 * 1024

    def __post_init__(self) -> None:
        if self.max_entries <= 0:
            raise ValueError("max_entries must be positive")
        if self.max_single_file_size <= 0 or self.max_total_size <= 0:
            raise ValueError("package size limits must be positive")
        if self.max_compression_ratio <= 0:
            raise ValueError("max_compression_ratio must be positive")
        if self.max_manifest_size <= 0:
            raise ValueError("max_manifest_size must be positive")


@dataclass(frozen=True)
class AppPackageMetadata:
    product: str
    version: SemanticVersion
    platform: str
    architecture: str
    entrypoint: str
    build_id: str

    @classmethod
    def from_bytes(cls, raw: bytes) -> "AppPackageMetadata":
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _package_invalid("app-manifest.json must be valid UTF-8 JSON") from exc
        if not isinstance(value, Mapping):
            raise _package_invalid("app-manifest.json must contain an object")

        def required_string(name: str) -> str:
            item = value.get(name)
            if not isinstance(item, str) or not item.strip():
                raise _package_invalid(f"app-manifest.json field {name!r} is invalid")
            return item

        try:
            version = SemanticVersion.parse(required_string("version"))
        except ValueError as exc:
            raise _package_invalid("app-manifest.json version is not semantic") from exc
        entrypoint = required_string("entrypoint")
        if "/" in entrypoint or "\\" in entrypoint:
            raise _package_invalid("app-manifest.json entrypoint must be a base filename")
        return cls(
            product=required_string("product"),
            version=version,
            platform=required_string("platform"),
            architecture=required_string("architecture"),
            entrypoint=entrypoint,
            build_id=required_string("build_id"),
        )


def _package_unsafe(message: str) -> UpdateError:
    return UpdateError(ErrorCode.UPDATE_PACKAGE_UNSAFE, message)


def _package_invalid(message: str) -> UpdateError:
    return UpdateError(ErrorCode.UPDATE_PACKAGE_INVALID, message)


def _normalized_member_path(filename: str) -> PurePosixPath:
    if not isinstance(filename, str) or not filename or "\x00" in filename:
        raise _package_unsafe("ZIP member has an invalid name")
    normalized = filename.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("//"):
        raise _package_unsafe(f"ZIP member uses an absolute or UNC path: {filename!r}")
    if _DRIVE_PATH_RE.match(normalized):
        raise _package_unsafe(f"ZIP member uses a drive path: {filename!r}")
    path = PurePosixPath(normalized)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise _package_unsafe(f"ZIP member escapes the package root: {filename!r}")
    for part in path.parts:
        if ":" in part or part.endswith((" ", ".")):
            raise _package_unsafe(f"ZIP member is not safe on Windows: {filename!r}")
        stem = part.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise _package_unsafe(f"ZIP member uses a reserved Windows name: {filename!r}")
    return path


def _is_special_member(info: zipfile.ZipInfo) -> bool:
    mode_type = (info.external_attr >> 16) & 0o170000
    return mode_type not in {0, stat.S_IFREG, stat.S_IFDIR}


def _inspect_members(
    archive: zipfile.ZipFile,
    limits: PackageLimits,
) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > limits.max_entries:
        raise _package_unsafe("ZIP contains too many entries")

    members: dict[str, zipfile.ZipInfo] = {}
    casefolded: dict[str, str] = {}
    file_paths: set[str] = set()
    total_size = 0

    for info in infos:
        path = _normalized_member_path(info.filename)
        normalized = path.as_posix()
        folded = normalized.casefold()
        previous = casefolded.get(folded)
        if previous is not None:
            raise _package_unsafe(
                f"ZIP contains duplicate Windows paths: {previous!r} and {normalized!r}"
            )
        casefolded[folded] = normalized
        if _is_special_member(info):
            raise _package_unsafe(f"ZIP contains a link or special file: {normalized!r}")

        is_directory = info.is_dir() or normalized.endswith("/")
        if not is_directory:
            if info.file_size > limits.max_single_file_size:
                raise _package_unsafe(f"ZIP member is too large: {normalized!r}")
            total_size += info.file_size
            if total_size > limits.max_total_size:
                raise _package_unsafe("ZIP expands beyond the allowed total size")
            if info.file_size > 0:
                if info.compress_size <= 0:
                    raise _package_unsafe(f"ZIP member has an invalid compressed size: {normalized!r}")
                ratio = info.file_size / info.compress_size
                if ratio > limits.max_compression_ratio:
                    raise _package_unsafe(
                        f"ZIP member exceeds the compression ratio limit: {normalized!r}"
                    )
            file_paths.add(folded)
        members[normalized] = info

    for folded_file in file_paths:
        parts = folded_file.split("/")
        for index in range(1, len(parts)):
            if "/".join(parts[:index]) in file_paths:
                raise _package_unsafe("ZIP contains a file/directory hierarchy collision")
        prefix = folded_file + "/"
        if any(other.startswith(prefix) for other in file_paths):
            raise _package_unsafe("ZIP contains a file/directory hierarchy collision")
    return members


def _read_metadata(
    archive: zipfile.ZipFile,
    members: Mapping[str, zipfile.ZipInfo],
    limits: PackageLimits,
) -> AppPackageMetadata:
    info = members.get("app-manifest.json")
    if info is None or info.is_dir():
        raise _package_invalid("package is missing app-manifest.json")
    if info.file_size > limits.max_manifest_size:
        raise _package_invalid("app-manifest.json is too large")
    with archive.open(info, "r") as stream:
        raw = stream.read(limits.max_manifest_size + 1)
    if len(raw) > limits.max_manifest_size:
        raise _package_invalid("app-manifest.json is too large")
    return AppPackageMetadata.from_bytes(raw)


def _validate_metadata(
    metadata: AppPackageMetadata,
    members: Mapping[str, zipfile.ZipInfo],
    *,
    expected_product: str,
    expected_version: str,
    expected_platform: str,
    expected_architecture: str,
    expected_entrypoint: str,
) -> None:
    try:
        expected_semver = SemanticVersion.parse(expected_version)
    except ValueError as exc:
        raise ValueError("expected_version must be a semantic version") from exc
    expected = {
        "product": expected_product,
        "version": expected_semver,
        "platform": expected_platform,
        "architecture": expected_architecture,
        "entrypoint": expected_entrypoint,
    }
    actual = {
        "product": metadata.product,
        "version": metadata.version,
        "platform": metadata.platform,
        "architecture": metadata.architecture,
        "entrypoint": metadata.entrypoint,
    }
    for name, expected_value in expected.items():
        if actual[name] != expected_value:
            raise _package_invalid(
                f"package {name} mismatch: expected {expected_value!s}, got {actual[name]!s}"
            )
    entrypoint_info = members.get(expected_entrypoint)
    if entrypoint_info is None or entrypoint_info.is_dir():
        raise _package_invalid(f"package is missing entrypoint {expected_entrypoint!r}")


def _destination_path(root: Path, member: PurePosixPath) -> Path:
    destination = root.joinpath(*member.parts)
    try:
        destination.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise _package_unsafe(f"ZIP member escapes staging root: {member.as_posix()!r}") from exc
    return destination


def extract_update_zip(
    package_path: str | Path,
    staging_root: str | Path,
    *,
    expected_product: str,
    expected_version: str,
    expected_platform: str,
    expected_architecture: str,
    expected_entrypoint: str,
    limits: PackageLimits | None = None,
) -> Path:
    """Validate and extract a package to a newly-created random staging folder."""

    package = Path(package_path)
    staging_parent = Path(staging_root)
    selected_limits = limits or PackageLimits()
    staging_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{expected_version}-", dir=staging_parent))
    try:
        try:
            archive = zipfile.ZipFile(package, "r")
        except (OSError, zipfile.BadZipFile) as exc:
            raise _package_invalid("update package is not a readable ZIP file") from exc
        with archive:
            members = _inspect_members(archive, selected_limits)
            metadata = _read_metadata(archive, members, selected_limits)
            _validate_metadata(
                metadata,
                members,
                expected_product=expected_product,
                expected_version=expected_version,
                expected_platform=expected_platform,
                expected_architecture=expected_architecture,
                expected_entrypoint=expected_entrypoint,
            )
            for normalized, info in members.items():
                destination = _destination_path(staging, PurePosixPath(normalized))
                if info.is_dir() or normalized.endswith("/"):
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, destination.open("xb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
        return staging
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
