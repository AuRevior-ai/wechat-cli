#!/usr/bin/env python3
"""Two-phase production release preparation entrypoint for Board 7 workflows.

The ``sign`` phase is the only phase that accepts a release private-key path.
The ``publish`` phase re-verifies prepared public assets under the production
trust profile and uses only the machine automation surface; release-state
mutation is intentionally absent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.production_release_workflow import publish_prepared_release  # noqa: E402
from wechat_cli.admin.client import AdminApiError  # noqa: E402
from wechat_cli.release.automation_client import (  # noqa: E402
    ReleaseAutomationClient,
    UrllibReleaseAutomationTransport,
)
from wechat_cli.release.builder import ReleaseBuildOptions  # noqa: E402
from wechat_cli.release.workflow import sign_release_for_workflow  # noqa: E402

def _published_at(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("published_at must include a timezone")
    return parsed


def sign_command(args: argparse.Namespace) -> dict[str, object]:
    if args.signing_key_id != "release-key-production-01":
        raise ValueError("production signing key id must be release-key-production-01")
    options = ReleaseBuildOptions(
        release_id=args.release_id,
        channel=args.channel,
        published_at=_published_at(args.published_at),
        minimum_app_version=args.minimum_app_version,
        minimum_launcher_version=args.minimum_launcher_version,
        signing_key_id=args.signing_key_id,
        release_summary=args.summary,
        release_notes_url=args.notes_url,
        rollout_percentage=0,
    )
    return sign_release_for_workflow(
        package_path=args.package,
        signing_key_path=args.signing_key,
        output_dir=args.output_dir,
        options=options,
    )


def probe_command(args: argparse.Namespace) -> dict[str, object]:
    client_id = os.environ.get("WECHAT_CLI_ACCESS_CLIENT_ID", "")
    client_secret = os.environ.get("WECHAT_CLI_ACCESS_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValueError("production automation credential is unavailable")

    transport = UrllibReleaseAutomationTransport(args.admin_origin)
    headers = {
        "CF-Access-Client-Id": client_id,
        "CF-Access-Client-Secret": client_secret,
    }
    client = ReleaseAutomationClient(
        json_transport=transport.json_request,
        upload_transport=transport.upload,
        header_provider=lambda: dict(headers),
    )
    releases = client.list_releases()

    with tempfile.TemporaryDirectory() as tmp:
        probe_path = Path(tmp) / "transport-probe.bin"
        probe_path.write_bytes(b"x")
        try:
            transport.upload(
                "/v1/automation/releases/rel_transport_probe/package",
                headers,
                probe_path,
                {
                    "X-Release-Channel": "stable",
                    "X-Package-Sha256": "invalid",
                    "X-Operation-Nonce": "transport-probe",
                    "Content-Length": "1",
                },
            )
        except AdminApiError as exc:
            if exc.code != "INVALID_REQUEST" or exc.status != 400:
                raise RuntimeError(
                    f"production automation PUT probe failed code={exc.code} status={exc.status}"
                ) from exc
        else:
            raise RuntimeError("production automation PUT probe was unexpectedly accepted")

    return {
        "ok": True,
        "release_count": len(releases),
        "put_probe_status": 400,
        "put_probe_code": "INVALID_REQUEST",
    }


def publish_command(args: argparse.Namespace) -> dict[str, object]:
    return publish_prepared_release(
        package_path=args.package,
        manifest_path=args.manifest,
        signature_path=args.signature,
        metadata_path=args.metadata,
        trust_profile_path=args.trust_profile,
        api_origin=args.api_origin,
        admin_origin=args.admin_origin,
        repository=args.github_repository,
        source_sha=args.source_sha,
        provenance_target_sha=args.provenance_target_sha,
        release_name=args.release_name,
        release_body=args.release_body,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="action", required=True)

    sign = subcommands.add_parser("sign", help="Sign one already-built production update package.")
    sign.add_argument("--package", type=Path, required=True)
    sign.add_argument("--signing-key", type=Path, required=True)
    sign.add_argument("--output-dir", type=Path, required=True)
    sign.add_argument("--release-id", required=True)
    sign.add_argument("--channel", choices=("stable", "beta"), required=True)
    sign.add_argument("--published-at", required=True)
    sign.add_argument("--minimum-app-version", required=True)
    sign.add_argument("--minimum-launcher-version", required=True)
    sign.add_argument("--signing-key-id", default="release-key-production-01")
    sign.add_argument("--summary", default="")
    sign.add_argument("--notes-url")

    probe = subcommands.add_parser(
        "probe",
        help="Verify the production automation Python transport without mutating release state.",
    )
    probe.add_argument("--admin-origin", required=True)

    publish = subcommands.add_parser(
        "publish",
        help="Publish already-signed public assets through GitHub provenance and machine automation.",
    )
    publish.add_argument("--package", type=Path, required=True)
    publish.add_argument("--manifest", type=Path, required=True)
    publish.add_argument("--signature", type=Path, required=True)
    publish.add_argument("--metadata", type=Path, required=True)
    publish.add_argument("--trust-profile", type=Path, required=True)
    publish.add_argument("--api-origin", required=True)
    publish.add_argument("--admin-origin", required=True)
    publish.add_argument("--github-repository", required=True)
    publish.add_argument("--source-sha", required=True)
    publish.add_argument("--provenance-target-sha", required=True)
    publish.add_argument("--release-name", required=True)
    publish.add_argument("--release-body", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.action == "sign":
            result = sign_command(args)
        elif args.action == "probe":
            result = probe_command(args)
        else:
            result = publish_command(args)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
