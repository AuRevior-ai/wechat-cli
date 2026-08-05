"""Prepare a verified update for installation on the next launcher start."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .client import UpdateCheckResult
from .download import DownloadRequest, download_update
from .errors import ErrorCode, UpdateError
from .layout import InstallLayout
from .manifest import verify_manifest_package
from .package import extract_update_zip
from .state import PendingUpdate, save_pending_update
from .versioning import SemanticVersion

DownloadFunction = Callable[[DownloadRequest, str | Path], Path]


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("prepared_at must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def prepare_checked_update(
    result: UpdateCheckResult,
    layout: InstallLayout,
    *,
    download_url: str,
    downloader: DownloadFunction = download_update,
    prepared_at: datetime | None = None,
) -> PendingUpdate:
    """Download, verify, safely extract, and mark a checked update as pending."""

    if not result.update_available:
        raise ValueError("update check result does not contain an update")
    if (
        result.manifest is None
        or result.raw_manifest is None
        or result.download_ticket is None
    ):
        raise ValueError("update check result is incomplete")

    manifest = result.manifest
    current = layout.load_current()
    if SemanticVersion.parse(str(manifest.version)) <= SemanticVersion.parse(
        current.current_version
    ):
        raise UpdateError(
            ErrorCode.UPDATE_PACKAGE_INVALID,
            "update target must be newer than the current version",
        )

    target = layout.version_path(str(manifest.version))
    if target.exists():
        raise UpdateError(
            ErrorCode.UPDATE_PACKAGE_INVALID,
            f"target version directory already exists: {target}",
        )

    layout.ensure_directories()
    request = DownloadRequest(
        download_url=download_url,
        download_ticket=result.download_ticket,
        release_id=manifest.release_id,
        version=str(manifest.version),
        filename=manifest.package.filename,
        expected_size=manifest.package.size,
        expected_sha256=manifest.package.sha256,
    )
    package_path = Path(downloader(request, layout.downloads_dir))
    verify_manifest_package(package_path, manifest)

    staging: Path | None = None
    moved = False
    try:
        staging = extract_update_zip(
            package_path,
            layout.staging_dir,
            expected_product=manifest.product,
            expected_version=str(manifest.version),
            expected_platform=manifest.platform,
            expected_architecture=manifest.architecture,
            expected_entrypoint=manifest.install.entrypoint,
        )
        if target.exists():
            raise UpdateError(
                ErrorCode.UPDATE_PACKAGE_INVALID,
                f"target version directory appeared during preparation: {target}",
            )
        os.replace(staging, target)
        moved = True
        timestamp = prepared_at or datetime.now(timezone.utc)
        pending = PendingUpdate(
            release_id=manifest.release_id,
            version=str(manifest.version),
            prepared_path=str(Path("versions") / str(manifest.version)),
            manifest_sha256=hashlib.sha256(result.raw_manifest).hexdigest(),
            prepared_at=_format_time(timestamp),
            install_on_next_start=True,
        )
        save_pending_update(layout.pending_update_path, pending)
        return pending
    except Exception:
        if moved and target.exists() and not layout.pending_update_path.exists():
            shutil.rmtree(target, ignore_errors=True)
        raise
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
