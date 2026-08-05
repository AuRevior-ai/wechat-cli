"""Transactional orchestration of GitHub assets and Worker release registration."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..admin.client import AdminApiClient
from .builder import SignedRelease
from .github import GitHubAsset, GitHubReleaseClient


class ReleaseAdminClient(Protocol):
    def register_release(self, payload): ...

    def update_release(
        self,
        release_id: str,
        *,
        enabled: bool | None = None,
        paused: bool | None = None,
        rollout_percentage: int | None = None,
        operation_nonce: str,
    ): ...


@dataclass(frozen=True)
class PublishedRelease:
    release_id: str
    version: str
    github_release_id: int
    package_asset_id: int
    manifest_asset_id: int
    signature_asset_id: int
    enabled: bool
    paused: bool


def _best_effort_github_rollback(
    github_client: GitHubReleaseClient,
    github_release_id: int | None,
    assets: list[GitHubAsset],
) -> None:
    for asset in reversed(assets):
        try:
            github_client.delete_asset(asset.asset_id)
        except Exception:
            pass
    if github_release_id is not None:
        try:
            github_client.delete_release(github_release_id)
        except Exception:
            pass


def publish_signed_release(
    signed: SignedRelease,
    *,
    github_client: GitHubReleaseClient,
    admin_client: ReleaseAdminClient | AdminApiClient,
    repository: str,
    target_commitish: str,
    release_name: str,
    release_body: str,
    operation_nonce: str,
    enable: bool = False,
    enable_operation_nonce: str | None = None,
    rollout_percentage: int = 100,
) -> PublishedRelease:
    """Create a draft release, upload assets, and register it with the Worker.

    The Worker record is created disabled and paused. Enabling is a distinct,
    explicit step so an upload can be inspected before clients are eligible.
    """

    if not isinstance(signed, SignedRelease):
        raise TypeError("signed must be a SignedRelease")
    if repository != github_client.repository:
        raise ValueError("repository does not match the GitHub client")
    if not operation_nonce or len(operation_nonce) < 8:
        raise ValueError("operation_nonce is invalid")
    if not 0 <= rollout_percentage <= 100:
        raise ValueError("rollout_percentage must be between 0 and 100")
    if enable and (
        not isinstance(enable_operation_nonce, str)
        or len(enable_operation_nonce) < 8
    ):
        raise ValueError("enable_operation_nonce is required when enabling")

    release_id: int | None = None
    uploaded: list[GitHubAsset] = []
    worker_registered = False
    try:
        release = github_client.create_release(
            tag_name=f"v{signed.version}",
            name=release_name,
            body=release_body,
            target_commitish=target_commitish,
            draft=True,
            prerelease=signed.channel == "beta",
        )
        release_id = release.release_id
        package_asset = github_client.upload_asset(
            release.upload_url,
            signed.package_path,
            content_type="application/zip",
        )
        uploaded.append(package_asset)

        with tempfile.TemporaryDirectory(prefix="wechat-cli-release-assets-") as tmp:
            root = Path(tmp)
            manifest_path = root / f"wechat-cli-update-manifest-{signed.version}.json"
            signature_path = root / f"wechat-cli-update-manifest-{signed.version}.sig"
            manifest_path.write_bytes(signed.manifest_bytes)
            signature_path.write_bytes(signed.signature)
            manifest_asset = github_client.upload_asset(
                release.upload_url,
                manifest_path,
                content_type="application/json",
            )
            uploaded.append(manifest_asset)
            signature_asset = github_client.upload_asset(
                release.upload_url,
                signature_path,
                content_type="application/octet-stream",
            )
            uploaded.append(signature_asset)

        payload = signed.registration_payload(
            github_repository=repository,
            github_release_id=str(release.release_id),
            github_asset_id=str(package_asset.asset_id),
            github_asset_name=package_asset.name,
            operation_nonce=operation_nonce,
            rollout_percentage=rollout_percentage,
        )
        registered = admin_client.register_release(payload)
        worker_registered = True
        enabled = bool(registered.get("enabled", False))
        paused = bool(registered.get("paused", True))
        if enable:
            updated = admin_client.update_release(
                signed.release_id,
                enabled=True,
                paused=False,
                rollout_percentage=rollout_percentage,
                operation_nonce=enable_operation_nonce,
            )
            enabled = bool(updated.get("enabled", True))
            paused = bool(updated.get("paused", False))
        return PublishedRelease(
            release_id=signed.release_id,
            version=signed.version,
            github_release_id=release.release_id,
            package_asset_id=package_asset.asset_id,
            manifest_asset_id=manifest_asset.asset_id,
            signature_asset_id=signature_asset.asset_id,
            enabled=enabled,
            paused=paused,
        )
    except Exception:
        # Before Worker registration, deleting the draft avoids orphaned assets.
        # After registration, preserve the private draft and registered metadata:
        # an enable failure must leave a recoverable disabled/paused release.
        if not worker_registered:
            _best_effort_github_rollback(
                github_client,
                release_id,
                uploaded,
            )
        raise
