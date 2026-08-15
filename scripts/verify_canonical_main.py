"""Fail closed unless a privileged workflow targets the exact observed canonical main SHA."""

from __future__ import annotations

import argparse
import json
import re

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _validated_sha(value: str, name: str) -> str:
    if not isinstance(value, str) or _FULL_SHA.fullmatch(value) is None:
        raise ValueError(f"{name} must be a full 40-character lowercase Git SHA")
    return value


def verify_canonical_main(
    *,
    requested_sha: str,
    checked_out_sha: str,
    observed_main_sha: str,
) -> str:
    requested = _validated_sha(requested_sha, "requested_sha")
    checked_out = _validated_sha(checked_out_sha, "checked_out_sha")
    observed_main = _validated_sha(observed_main_sha, "observed_main_sha")
    if requested != checked_out or requested != observed_main:
        raise ValueError("requested, checked-out, and observed canonical main SHAs must match exactly")
    return requested


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requested-sha", required=True)
    parser.add_argument("--checked-out-sha", required=True)
    parser.add_argument("--observed-main-sha", required=True)
    args = parser.parse_args(argv)
    source_sha = verify_canonical_main(
        requested_sha=args.requested_sha,
        checked_out_sha=args.checked_out_sha,
        observed_main_sha=args.observed_main_sha,
    )
    print(json.dumps({"canonical_main_sha": source_sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
