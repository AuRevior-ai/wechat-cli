"""Transactional orchestration of GitHub assets and Worker release registration."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .builder import SignedRelease
from .github import GitHubAsset, GitHubReleaseClient


class ReleaseAdminClient(Protocol):
    def upload_release_package(
        self,
        release_id: str,
        *,
        channel: str,
        package_path: str | Path,
        package_sha256: str,
        operation_nonce: str,
    ): ...

    def register_release(self, payload): ...


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
    admin_client: ReleaseAdminClient,
    repository: str,
    target_commitish: str,
    release_name: str,
    release_body: str,
    operation_nonce: str,
    upload_operation_nonce: str,
    enable: bool = False,
    enable_operation_nonce: str | None = None,
    rollout_percentage: int = 100,
) -> PublishedRelease:
    """Prepare R2 transport, publish immutable GitHub provenance, then register disabled.

    Enabling is deliberately not part of this orchestration. It remains a separate
    independently authorized operation after registration and read-only reconcile.
    """

    if not isinstance(signed, SignedRelease):
        raise TypeError("signed must be a SignedRelease")
    if repository != github_client.repository:
        raise ValueError("repository does not match the GitHub client")
    if not operation_nonce or len(operation_nonce) < 8:
        raise ValueError("operation_nonce is invalid")
    if not 0 <= rollout_percentage <= 100:
        raise ValueError("rollout_percentage must be between 0 and 100")
    if not isinstance(upload_operation_nonce, str) or len(upload_operation_nonce) < 8:
        raise ValueError("upload_operation_nonce is invalid")
    if enable:
        raise ValueError("release enablement is a separate independently authorized operation")
    if enable_operation_nonce is not None:
        raise ValueError("enable_operation_nonce is not accepted during publication")

    release_id: int | None = None
    uploaded: list[GitHubAsset] = []
    github_published = False
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

        readiness = admin_client.upload_release_package(
            signed.release_id,
            channel=signed.channel,
            package_path=signed.package_path,
            package_sha256=signed.package_sha256,
            operation_nonce=upload_operation_nonce,
        )
        if readiness.get("ready") is not True:
            raise RuntimeError("R2 release package readiness was not confirmed")
        if readiness.get("distribution_backend") != "r2":
            raise RuntimeError("R2 release package returned another distribution backend")
        object_key = readiness.get("distribution_object_key")
        if not isinstance(object_key, str) or not object_key:
            raise RuntimeError("R2 release package object key is missing")
        if readiness.get("package_sha256") != signed.package_sha256:
            raise RuntimeError("R2 release package hash drifted")
        if readiness.get("package_size") != signed.package_size:
            raise RuntimeError("R2 release package size drifted")

        published = github_client.publish_release(
            release.release_id,
            prerelease=signed.channel == "beta",
            make_latest=False,
        )
        if published.draft:
            raise RuntimeError("GitHub provenance release remained a draft")
        github_published = True

        payload = signed.registration_payload(
            github_repository=repository,
            github_release_id=str(release.release_id),
            github_asset_id=str(package_asset.asset_id),
            github_asset_name=package_asset.name,
            operation_nonce=operation_nonce,
            rollout_percentage=rollout_percentage,
            distribution_backend="r2",
            distribution_object_key=object_key,
        )
        registered = admin_client.register_release(payload)
        enabled = bool(registered.get("enabled", False))
        paused = bool(registered.get("paused", True))
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
        # Before immutable GitHub publication, the Draft and its assets are disposable.
        # After publication, preserve immutable provenance and the already-readied R2
        # object even if Worker registration fails; no client can select it without a row.
        if not github_published:
            _best_effort_github_rollback(
                github_client,
                release_id,
                uploaded,
            )
        raise
