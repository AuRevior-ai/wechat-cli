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
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.production_release_workflow import publish_prepared_release  # noqa: E402
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
        result = sign_command(args) if args.action == "sign" else publish_command(args)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
