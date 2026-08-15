#!/usr/bin/env python3
"""Board 6 G5 live staging behavior acceptance without secret output.

Permanent license keys, device tokens, and download tickets are read/created only in
process memory. The emitted JSON contains only safe identifiers, hashes, sizes, and
acceptance outcomes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.packaging_paths import assert_outside_repository
except ModuleNotFoundError:  # Direct execution fallback.
    from packaging_paths import assert_outside_repository

from wechat_cli.license.client import LicenseApiClient, UrllibJsonTransport
from wechat_cli.update.client import UpdateApiClient, UpdateCheckResult
from wechat_cli.update.crypto import TrustedEd25519Keys
from wechat_cli.update.download import DownloadRequest, download_update
from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.update.models import FailedReleaseIdentity
from wechat_cli.version import APP_VERSION


class AcceptanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class LicenseCsvRecord:
    license_id: str
    license_key: str = field(repr=False)
    license_hint: str
    release_channel: str


def read_single_license_csv(path: str | Path) -> LicenseCsvRecord:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("license CSV must be an existing regular file")
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 1:
        raise ValueError("acceptance license CSV must contain exactly one row")
    row = rows[0]
    license_id = str(row.get("license_id") or "").strip()
    license_key = str(row.get("license_key") or "").strip()
    license_hint = str(row.get("license_hint") or "").strip()
    channel = str(row.get("release_channel") or "").strip()
    if not license_id or not license_key or len(license_hint) != 4 or channel not in {"stable", "beta"}:
        raise ValueError("acceptance license CSV is invalid")
    return LicenseCsvRecord(license_id, license_key, license_hint, channel)


def _device_spec(license_id: str, channel: str) -> tuple[str, str, str]:
    seed = f"board6-g5\0{license_id}\0{channel}".encode("utf-8")
    identity = hashlib.sha256(seed).hexdigest()
    fingerprint = hashlib.sha256(b"fingerprint\0" + seed).hexdigest()
    return f"dev_b6g5_{identity[:32]}", fingerprint, f"BOARD6-G5-{channel.upper()}"


def _check(
    update_client: UpdateApiClient,
    *,
    device_token: str,
    device_id: str,
    channel: str,
    failed_releases: list[FailedReleaseIdentity] | None = None,
) -> UpdateCheckResult:
    return update_client.check(
        device_token=device_token,
        current_version="0.5.1",
        launcher_version="0.1.0",
        channel=channel,
        platform="windows",
        architecture="x86_64",
        product="wechat-cli-web",
        device_id=device_id,
        failed_versions=[],
        failed_releases=failed_releases or [],
    )


def _expect_channel_mismatch(action: Callable[[], object]) -> str:
    try:
        action()
    except Exception as exc:
        code = getattr(getattr(exc, "code", None), "value", None)
        if code != ErrorCode.UPDATE_CHANNEL_MISMATCH.value:
            raise AcceptanceError(f"channel mismatch returned unexpected error: {code!r}") from exc
        if getattr(exc, "retryable", None) is not False:
            raise AcceptanceError("channel mismatch must be non-retryable") from exc
        return code
    raise AcceptanceError("channel mismatch unexpectedly succeeded")


def _assert_candidate(
    result: UpdateCheckResult,
    *,
    expected_release_id: str,
    expected_version: str,
    expected_manifest_sha256: str,
    expected_package_sha256: str,
    expected_package_size: int,
) -> None:
    if not result.update_available or result.manifest is None or not result.download_ticket:
        raise AcceptanceError("expected beta candidate was not selectable")
    manifest = result.manifest
    if manifest.release_id != expected_release_id or str(manifest.version) != expected_version:
        raise AcceptanceError("selected release identity drifted")
    if hashlib.sha256(result.raw_manifest or b"").hexdigest() != expected_manifest_sha256:
        raise AcceptanceError("selected manifest hash drifted")
    if manifest.package.sha256 != expected_package_sha256 or manifest.package.size != expected_package_size:
        raise AcceptanceError("selected package metadata drifted")


def _default_range_probe(
    *, api_url: str, ticket: str, expected_size: int, **_: object
) -> dict[str, object]:
    request = Request(
        api_url.rstrip("/") + "/v1/updates/download",
        headers={
            "Accept": "application/octet-stream",
            "Authorization": f"Download {ticket}",
            "Range": "bytes=0-0",
            "User-Agent": f"WeChatCliUpdate/{APP_VERSION}",
        },
        method="GET",
    )
    with urlopen(request, timeout=30.0) as response:
        body = response.read(2)
        status = int(response.status)
        content_range = response.headers.get("Content-Range")
    if status != 206 or body is None or len(body) != 1:
        raise AcceptanceError("R2 one-byte range probe failed")
    expected_range = f"bytes 0-0/{expected_size}"
    if content_range != expected_range:
        raise AcceptanceError("R2 Content-Range drifted")
    return {"status": status, "content_range": content_range}


def _default_full_download(
    *,
    api_url: str,
    ticket: str,
    manifest: Any,
    download_dir: Path,
    **_: object,
) -> dict[str, object]:
    request = DownloadRequest(
        download_url=api_url.rstrip("/") + "/v1/updates/download",
        download_ticket=ticket,
        release_id=manifest.release_id,
        version=str(manifest.version),
        filename=manifest.package.filename,
        expected_size=manifest.package.size,
        expected_sha256=manifest.package.sha256,
    )
    path = download_update(request, download_dir)
    return {
        "size": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "path": str(path),
    }


def run_acceptance(
    *,
    stable_license: LicenseCsvRecord,
    beta_license: LicenseCsvRecord,
    license_client: Any,
    update_client: Any,
    expected_release_id: str,
    expected_version: str,
    expected_manifest_sha256: str,
    expected_package_sha256: str,
    expected_package_size: int,
    range_probe: Callable[..., dict[str, object]],
    full_download: Callable[..., dict[str, object]],
    api_url: str = "https://api.example.invalid",
    download_dir: Path | None = None,
) -> dict[str, object]:
    if stable_license.release_channel != "stable" or beta_license.release_channel != "beta":
        raise AcceptanceError("acceptance license channels are not stable/beta as expected")

    stable_device_id, stable_fingerprint, stable_name = _device_spec(
        stable_license.license_id, "stable"
    )
    beta_device_id, beta_fingerprint, beta_name = _device_spec(beta_license.license_id, "beta")

    stable_activation = license_client.activate(
        license_key=stable_license.license_key,
        device_id=stable_device_id,
        device_fingerprint=stable_fingerprint,
        device_name=stable_name,
        app_version="0.5.1",
        launcher_version="0.1.0",
    )
    beta_activation = license_client.activate(
        license_key=beta_license.license_key,
        device_id=beta_device_id,
        device_fingerprint=beta_fingerprint,
        device_name=beta_name,
        app_version="0.5.1",
        launcher_version="0.1.0",
    )
    if stable_activation.license_id != stable_license.license_id:
        raise AcceptanceError("stable activation returned another license")
    if beta_activation.license_id != beta_license.license_id:
        raise AcceptanceError("beta activation returned another license")

    stable_aligned = _check(
        update_client,
        device_token=stable_activation.device_token,
        device_id=stable_device_id,
        channel="stable",
    )
    if stable_aligned.update_available:
        raise AcceptanceError("stable 0.5.1 unexpectedly received a newer stable candidate")

    stable_mismatch_code = _expect_channel_mismatch(
        lambda: _check(
            update_client,
            device_token=stable_activation.device_token,
            device_id=stable_device_id,
            channel="beta",
        )
    )
    beta_mismatch_code = _expect_channel_mismatch(
        lambda: _check(
            update_client,
            device_token=beta_activation.device_token,
            device_id=beta_device_id,
            channel="stable",
        )
    )

    beta_aligned = _check(
        update_client,
        device_token=beta_activation.device_token,
        device_id=beta_device_id,
        channel="beta",
    )
    _assert_candidate(
        beta_aligned,
        expected_release_id=expected_release_id,
        expected_version=expected_version,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_package_sha256=expected_package_sha256,
        expected_package_size=expected_package_size,
    )

    wrong_hash = "0" * 64 if expected_manifest_sha256 != "0" * 64 else "1" * 64
    wrong_hash_result = _check(
        update_client,
        device_token=beta_activation.device_token,
        device_id=beta_device_id,
        channel="beta",
        failed_releases=[FailedReleaseIdentity(expected_version, wrong_hash)],
    )
    _assert_candidate(
        wrong_hash_result,
        expected_release_id=expected_release_id,
        expected_version=expected_version,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_package_sha256=expected_package_sha256,
        expected_package_size=expected_package_size,
    )

    exact_suppressed = _check(
        update_client,
        device_token=beta_activation.device_token,
        device_id=beta_device_id,
        channel="beta",
        failed_releases=[FailedReleaseIdentity(expected_version, expected_manifest_sha256)],
    )
    if exact_suppressed.update_available:
        raise AcceptanceError("exact failed release identity was not suppressed")

    range_result = range_probe(
        api_url=api_url,
        ticket=beta_aligned.download_ticket,
        manifest=beta_aligned.manifest,
        expected_size=expected_package_size,
    )

    fresh_for_download = _check(
        update_client,
        device_token=beta_activation.device_token,
        device_id=beta_device_id,
        channel="beta",
    )
    _assert_candidate(
        fresh_for_download,
        expected_release_id=expected_release_id,
        expected_version=expected_version,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_package_sha256=expected_package_sha256,
        expected_package_size=expected_package_size,
    )
    download_result = full_download(
        api_url=api_url,
        ticket=fresh_for_download.download_ticket,
        manifest=fresh_for_download.manifest,
        download_dir=download_dir or Path.cwd(),
    )
    if download_result.get("size") != expected_package_size:
        raise AcceptanceError("full R2 download size drifted")
    if download_result.get("sha256") != expected_package_sha256:
        raise AcceptanceError("full R2 download hash drifted")

    return {
        "stable_license_id": stable_license.license_id,
        "stable_license_hint": stable_license.license_hint,
        "stable_device_id": stable_device_id,
        "stable_aligned_update_available": False,
        "stable_mismatch_code": stable_mismatch_code,
        "beta_license_id": beta_license.license_id,
        "beta_license_hint": beta_license.license_hint,
        "beta_device_id": beta_device_id,
        "beta_mismatch_code": beta_mismatch_code,
        "beta_release_id": expected_release_id,
        "beta_version": expected_version,
        "beta_manifest_sha256": expected_manifest_sha256,
        "beta_package_sha256": expected_package_sha256,
        "beta_package_size": expected_package_size,
        "wrong_manifest_hash_remains_selectable": True,
        "exact_failed_release_suppressed": True,
        "r2_range_status": range_result.get("status"),
        "r2_content_range": range_result.get("content_range"),
        "r2_full_download_size": download_result.get("size"),
        "r2_full_download_sha256": download_result.get("sha256"),
    }


def _load_release_keys(path: Path) -> TrustedEd25519Keys:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    keys = value.get("release_public_keys") if isinstance(value, dict) else None
    if not isinstance(keys, dict) or not keys:
        raise ValueError("release public-key registry is invalid")
    return TrustedEd25519Keys.from_base64(keys)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Board 6 G5 staging behavior acceptance.")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--stable-license-csv", type=Path, required=True)
    parser.add_argument("--beta-license-csv", type=Path, required=True)
    parser.add_argument("--public-keys-file", type=Path, required=True)
    parser.add_argument("--download-dir", type=Path, required=True)
    parser.add_argument("--expected-release-id", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-package-sha256", required=True)
    parser.add_argument("--expected-package-size", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    download_dir = assert_outside_repository(args.download_dir, repository_root=ROOT)
    download_dir.mkdir(parents=True, exist_ok=True)
    transport = UrllibJsonTransport(args.api_url, timeout_seconds=20.0)
    license_client = LicenseApiClient(transport)
    update_client = UpdateApiClient(transport, trusted_keys=_load_release_keys(args.public_keys_file))
    summary = run_acceptance(
        stable_license=read_single_license_csv(args.stable_license_csv),
        beta_license=read_single_license_csv(args.beta_license_csv),
        license_client=license_client,
        update_client=update_client,
        expected_release_id=args.expected_release_id,
        expected_version=args.expected_version,
        expected_manifest_sha256=args.expected_manifest_sha256.lower(),
        expected_package_sha256=args.expected_package_sha256.lower(),
        expected_package_size=args.expected_package_size,
        range_probe=_default_range_probe,
        full_download=_default_full_download,
        api_url=args.api_url,
        download_dir=download_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
