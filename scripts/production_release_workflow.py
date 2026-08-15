"""Machine-only publication orchestration for the Board 7 production workflow."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from wechat_cli.release.automation_client import (
    ReleaseAutomationClient,
    UrllibReleaseAutomationTransport,
)
from wechat_cli.release.github import GitHubReleaseClient
from wechat_cli.release.publisher import publish_signed_release
from wechat_cli.release.workflow import load_prepared_release

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"required workflow credential is missing: {name}")
    return value.strip()


def _full_sha(value: str, label: str) -> str:
    if not isinstance(value, str) or _FULL_SHA.fullmatch(value) is None:
        raise ValueError(f"{label} must be 40 lowercase hexadecimal characters")
    return value


def publish_prepared_release(
    *,
    package_path: Path,
    manifest_path: Path,
    signature_path: Path,
    metadata_path: Path,
    trust_profile_path: Path,
    api_origin: str,
    admin_origin: str,
    repository: str,
    source_sha: str,
    provenance_target_sha: str,
    release_name: str,
    release_body: str,
) -> dict[str, object]:
    """Publish verified public assets without access to the release signing key."""

    source = _full_sha(source_sha, "production source SHA")
    provenance_target = _full_sha(
        provenance_target_sha,
        "release provenance target SHA",
    )
    github_token = _required_env("WECHAT_CLI_GITHUB_APP_TOKEN")
    access_client_id = _required_env("WECHAT_CLI_ACCESS_CLIENT_ID")
    access_client_secret = _required_env("WECHAT_CLI_ACCESS_CLIENT_SECRET")

    signed = load_prepared_release(
        package_path=package_path,
        manifest_path=manifest_path,
        signature_path=signature_path,
        metadata_path=metadata_path,
        trust_profile_path=trust_profile_path,
        expected_api_origin=api_origin,
    )
    github = GitHubReleaseClient(repository=repository, token=github_token)
    transport = UrllibReleaseAutomationTransport(admin_origin)
    automation = ReleaseAutomationClient(
        json_transport=transport.json_request,
        upload_transport=transport.upload,
        header_provider=lambda: {
            "CF-Access-Client-Id": access_client_id,
            "CF-Access-Client-Secret": access_client_secret,
        },
    )
    provenance_body = f"Source commit: {source}\n\n{release_body}"
    published = publish_signed_release(
        signed,
        github_client=github,
        admin_client=automation,
        repository=repository,
        target_commitish=provenance_target,
        release_name=release_name,
        release_body=provenance_body,
        operation_nonce="op_register_" + uuid.uuid4().hex,
        upload_operation_nonce="op_upload_" + uuid.uuid4().hex,
        enable=False,
        rollout_percentage=100,
    )
    if published.enabled or not published.paused:
        raise RuntimeError("production automation registration did not remain disabled and paused")
    return {
        "release_id": published.release_id,
        "version": published.version,
        "github_release_id": published.github_release_id,
        "enabled": published.enabled,
        "paused": published.paused,
        "source_sha": source,
        "provenance_target_sha": provenance_target,
    }
