#!/usr/bin/env python3
"""Run API-level end-to-end checks against a disposable local Worker.

The caller supplies a local API URL and a disposable administrator token. The
script never prints license keys, device tokens, administrator tokens, or
other credential material.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ApiFailure(Exception):
    status: int
    payload: Mapping[str, Any]

    def __str__(self) -> str:
        error = self.payload.get("error")
        data = error if isinstance(error, Mapping) else {}
        return f"HTTP {self.status}: {data.get('code')} {data.get('message')}"


def request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    authorization: str | None = None,
    payload: Mapping[str, Any] | None = None,
    body: bytes | None = None,
    content_type: str = "application/json",
) -> tuple[int, Mapping[str, Any]]:
    if payload is not None and body is not None:
        raise ValueError("payload and body are mutually exclusive")
    headers = {"Accept": "application/json"}
    raw = body
    if payload is not None:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if raw is not None:
        headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(raw))
    if authorization:
        headers["Authorization"] = authorization
    request = Request(base_url + path, data=raw, headers=headers, method=method)
    try:
        response = urlopen(request, timeout=30)
    except HTTPError as exc:
        response = exc
    with response:
        raw_response = response.read(4 * 1024 * 1024 + 1)
        status = int(response.status)
    value = json.loads(raw_response.decode("utf-8")) if raw_response else {}
    if not isinstance(value, Mapping):
        raise RuntimeError("API response root is not an object")
    if not 200 <= status < 300:
        raise ApiFailure(status, value)
    return status, value


def operation_nonce() -> str:
    return "e2e_" + uuid.uuid4().hex


def diagnostic_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("contents.txt", "local disposable diagnostic check\n")
    return buffer.getvalue()


def expect_failure(
    expected_status: int,
    expected_code: str,
    operation: Any,
) -> ApiFailure:
    try:
        operation()
    except ApiFailure as exc:
        error = exc.payload.get("error")
        code = error.get("code") if isinstance(error, Mapping) else None
        if exc.status != expected_status or code != expected_code:
            raise
        return exc
    raise RuntimeError(f"operation unexpectedly succeeded; expected {expected_code}")


def run(base_url: str, admin_token: str) -> dict[str, Any]:
    admin = f"Admin {admin_token}"
    _, created = request_json(
        base_url,
        "POST",
        "/v1/admin/licenses",
        authorization=admin,
        payload={
            "maximum_devices": 3,
            "release_channel": "stable",
            "contacts": {"email": "local-e2e@example.invalid"},
            "operation_nonce": operation_nonce(),
        },
    )
    license_id = str(created["license_id"])
    license_key = str(created["license_key"])

    def activate(index: int) -> Mapping[str, Any]:
        _, activation = request_json(
            base_url,
            "POST",
            "/v1/licenses/activate",
            payload={
                "license_key": license_key,
                "device_id": f"dev_local_e2e_{index:08d}",
                "device_fingerprint": f"{index:02x}" * 32,
                "device_name": f"LOCAL-E2E-{index}",
                "app_version": "0.5.0",
                "launcher_version": "0.1.0",
            },
        )
        return activation

    activations = [activate(index) for index in range(1, 4)]
    first = activations[0]
    first_device_id = str(first["device_id"])
    first_device_token = str(first["device_token"])
    bearer = f"Bearer {first_device_token}"

    expect_failure(409, "DEVICE_LIMIT_REACHED", lambda: activate(4))

    _, validation = request_json(
        base_url,
        "POST",
        "/v1/devices/validate",
        authorization=bearer,
        payload={"app_version": "0.5.0", "launcher_version": "0.1.0"},
    )
    if validation.get("license_id") != license_id:
        raise RuntimeError("validation license ID mismatch")
    if validation.get("device_id") != first_device_id:
        raise RuntimeError("validation device ID mismatch")
    if not validation.get("lease_content_base64"):
        raise RuntimeError("validation did not return an offline lease")

    _, devices = request_json(
        base_url,
        "GET",
        "/v1/devices",
        authorization=bearer,
    )
    listed = devices.get("devices", [])
    if not isinstance(listed, list) or len(listed) != 3:
        raise RuntimeError("device listing did not return all three active devices")

    second_device_id = str(activations[1]["device_id"])
    third_device_id = str(activations[2]["device_id"])
    request_json(
        base_url,
        "PATCH",
        f"/v1/devices/{second_device_id}",
        authorization=bearer,
        payload={
            "display_name": "RENAMED-E2E-DEVICE",
            "operation_nonce": operation_nonce(),
        },
    )
    request_json(
        base_url,
        "POST",
        f"/v1/devices/{third_device_id}/unbind",
        authorization=bearer,
        payload={
            "target_device_id": third_device_id,
            "operation_nonce": operation_nonce(),
        },
    )
    replacement = activate(4)
    if replacement.get("device_count") != 3:
        raise RuntimeError("unbinding did not immediately free one device slot")

    _, devices_after = request_json(
        base_url,
        "GET",
        "/v1/devices",
        authorization=bearer,
    )
    listed_after = devices_after.get("devices", [])
    if not isinstance(listed_after, list):
        raise RuntimeError("device listing response is invalid")
    if not any(
        isinstance(item, Mapping)
        and item.get("device_id") == second_device_id
        and item.get("display_name") == "RENAMED-E2E-DEVICE"
        for item in listed_after
    ):
        raise RuntimeError("renamed device was not returned by the listing")

    _, update = request_json(
        base_url,
        "POST",
        "/v1/updates/check",
        authorization=bearer,
        payload={
            "current_version": "0.5.0",
            "launcher_version": "0.1.0",
            "channel": "stable",
            "platform": "windows",
            "architecture": "x86_64",
            "product": "wechat-cli-web",
            "device_id": first_device_id,
            "failed_versions": [],
        },
    )
    if update.get("update_available") is not False:
        raise RuntimeError("empty local database unexpectedly returned an update")

    release_id = "rel_local_e2e_0501"
    package_sha256 = "22" * 32
    package_size = 123
    manifest_content = json.dumps(
        {
            "schema_version": 1,
            "product": "wechat-cli-web",
            "release_id": release_id,
            "version": "0.5.1",
            "channel": "stable",
            "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "platform": "windows",
            "architecture": "x86_64",
            "package": {
                "filename": "wechat-cli-app-0.5.1-win-x64.zip",
                "size": package_size,
                "sha256": package_sha256,
                "format": "zip",
            },
            "compatibility": {
                "minimum_app_version": "0.5.0",
                "minimum_launcher_version": "0.1.0",
                "maximum_launcher_version": None,
            },
            "install": {
                "entrypoint": "wechat-cli.exe",
                "health_endpoint": "/api/health",
                "health_timeout_seconds": 30,
            },
            "rollout": {
                "enabled": True,
                "percentage": 100,
                "seed": "local-e2e",
                "paused": False,
            },
            "update_policy": {
                "forced": False,
                "force_after": None,
                "minimum_allowed_version": None,
            },
            "launcher_update": None,
            "release_notes": {"summary": "Local E2E", "url": None},
            "signing": {"algorithm": "Ed25519", "key_id": "release-local-e2e"},
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    manifest_signature = os.urandom(64)
    request_json(
        base_url,
        "POST",
        "/v1/admin/releases",
        authorization=admin,
        payload={
            "release_id": release_id,
            "version": "0.5.1",
            "channel": "stable",
            "manifest_content_base64": base64.b64encode(manifest_content).decode("ascii"),
            "manifest_signature_base64": base64.b64encode(manifest_signature).decode("ascii"),
            "manifest_sha256": hashlib.sha256(manifest_content).hexdigest(),
            "package_sha256": package_sha256,
            "package_size": package_size,
            "github_repository": "local/e2e",
            "github_release_id": "5001",
            "github_asset_id": "6001",
            "github_asset_name": "wechat-cli-app-0.5.1-win-x64.zip",
            "rollout_percentage": 100,
            "rollout_seed": "local-e2e-rollout",
            "operation_nonce": operation_nonce(),
        },
    )
    request_json(
        base_url,
        "PATCH",
        f"/v1/admin/releases/{release_id}",
        authorization=admin,
        payload={
            "enabled": True,
            "paused": False,
            "operation_nonce": operation_nonce(),
        },
    )
    _, available_update = request_json(
        base_url,
        "POST",
        "/v1/updates/check",
        authorization=bearer,
        payload={
            "current_version": "0.5.0",
            "launcher_version": "0.1.0",
            "channel": "stable",
            "platform": "windows",
            "architecture": "x86_64",
            "product": "wechat-cli-web",
            "device_id": first_device_id,
            "failed_versions": [],
        },
    )
    if available_update.get("update_available") is not True:
        raise RuntimeError("enabled local release was not offered")
    manifest = available_update.get("manifest")
    if not isinstance(manifest, Mapping):
        raise RuntimeError("update response omitted signed manifest")
    if base64.b64decode(str(manifest.get("content_base64"))) != manifest_content:
        raise RuntimeError("update response changed the original manifest bytes")
    if base64.b64decode(str(manifest.get("signature_base64"))) != manifest_signature:
        raise RuntimeError("update response changed the manifest signature")
    download_ticket = str(available_update.get("download_ticket", ""))
    if not download_ticket.startswith("dlt_dl_"):
        raise RuntimeError("update response omitted a valid download ticket")

    request_json(
        base_url,
        "PATCH",
        f"/v1/admin/releases/{release_id}",
        authorization=admin,
        payload={"paused": True, "operation_nonce": operation_nonce()},
    )
    expect_failure(
        403,
        "UPDATE_PAUSED",
        lambda: request_json(
            base_url,
            "GET",
            "/v1/updates/download",
            authorization=f"Download {download_ticket}",
        ),
    )
    request_json(
        base_url,
        "PATCH",
        f"/v1/admin/releases/{release_id}",
        authorization=admin,
        payload={"paused": False, "operation_nonce": operation_nonce()},
    )
    _, failed_version_update = request_json(
        base_url,
        "POST",
        "/v1/updates/check",
        authorization=bearer,
        payload={
            "current_version": "0.5.0",
            "launcher_version": "0.1.0",
            "channel": "stable",
            "platform": "windows",
            "architecture": "x86_64",
            "product": "wechat-cli-web",
            "device_id": first_device_id,
            "failed_versions": ["0.5.1"],
        },
    )
    if failed_version_update.get("update_available") is not False:
        raise RuntimeError("failed version suppression was not honored")

    bundle = diagnostic_zip()
    digest = hashlib.sha256(bundle).hexdigest()
    _, session = request_json(
        base_url,
        "POST",
        "/v1/diagnostics/sessions",
        authorization=bearer,
        payload={
            "client_version": "0.5.0",
            "launcher_version": "0.1.0",
            "size_bytes": len(bundle),
            "sha256": digest,
        },
    )
    submission_id = str(session["submission_id"])
    _, uploaded = request_json(
        base_url,
        "PUT",
        str(session["upload_url"]),
        authorization=f"Diagnostic {session['upload_token']}",
        body=bundle,
        content_type="application/zip",
    )
    if uploaded.get("status") != "complete" or uploaded.get("sha256") != digest:
        raise RuntimeError("diagnostic upload completion did not match the bundle")

    _, diagnostics = request_json(
        base_url,
        "GET",
        "/v1/admin/diagnostics",
        authorization=admin,
    )
    if not any(
        item.get("submission_id") == submission_id
        for item in diagnostics.get("diagnostics", [])
        if isinstance(item, Mapping)
    ):
        raise RuntimeError("administrator diagnostics listing omitted the upload")

    _, contact_status = request_json(
        base_url,
        "GET",
        "/v1/admin/contact-encryption/status",
        authorization=admin,
    )
    if contact_status.get("current_key_version") != 1:
        raise RuntimeError("contact encryption key status is unexpected")

    request_json(
        base_url,
        "PATCH",
        f"/v1/admin/licenses/{license_id}/status",
        authorization=admin,
        payload={"status": "suspended", "operation_nonce": operation_nonce()},
    )
    expect_failure(
        403,
        "LICENSE_SUSPENDED",
        lambda: request_json(
            base_url,
            "POST",
            "/v1/devices/validate",
            authorization=bearer,
            payload={"app_version": "0.5.0", "launcher_version": "0.1.0"},
        ),
    )

    request_json(
        base_url,
        "PATCH",
        f"/v1/admin/licenses/{license_id}/status",
        authorization=admin,
        payload={"status": "active", "operation_nonce": operation_nonce()},
    )
    request_json(
        base_url,
        "POST",
        "/v1/devices/validate",
        authorization=bearer,
        payload={"app_version": "0.5.0", "launcher_version": "0.1.0"},
    )
    request_json(
        base_url,
        "DELETE",
        f"/v1/admin/diagnostics/{submission_id}",
        authorization=admin,
    )
    request_json(
        base_url,
        "PATCH",
        f"/v1/admin/licenses/{license_id}/status",
        authorization=admin,
        payload={"status": "revoked", "operation_nonce": operation_nonce()},
    )
    expect_failure(
        403,
        "LICENSE_REVOKED",
        lambda: request_json(
            base_url,
            "POST",
            "/v1/devices/validate",
            authorization=bearer,
            payload={"app_version": "0.5.0", "launcher_version": "0.1.0"},
        ),
    )

    return {
        "ok": True,
        "license_created": True,
        "three_device_limit_enforced": True,
        "rename_and_immediate_unbind_rebind": True,
        "offline_lease_issued": True,
        "update_lifecycle": "no-update, available, ticket, pause, failed-version-suppression",
        "diagnostic_uploaded_and_deleted": True,
        "suspension_and_revocation_enforced": True,
    }


def main() -> None:
    base_url = os.environ.get("WECHAT_CLI_E2E_BASE_URL", "http://127.0.0.1:8799").rstrip(
        "/"
    )
    admin_token = os.environ.get("WECHAT_CLI_E2E_ADMIN_TOKEN")
    if not admin_token:
        raise SystemExit("WECHAT_CLI_E2E_ADMIN_TOKEN is required")
    result = run(base_url, admin_token)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
