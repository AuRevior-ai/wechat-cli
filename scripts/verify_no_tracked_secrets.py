"""Reject high-confidence credential/private-key shapes in tracked non-test files."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{24,})\b")),
    ("admin-session", re.compile(r"\bwcas_[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._~-]{24,}\b")),
    ("legacy-admin", re.compile(r"\bwcadmin_[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._~-]{24,}\b")),
    ("license-key", re.compile(r"\bWCL-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3}\b")),
)


def scan_text(text: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in _PATTERNS if pattern.search(text))


def _excluded(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("tests/") or normalized.startswith(
        "services/license-update-worker/test/"
    )


def tracked_findings(root: str | Path) -> list[tuple[str, tuple[str, ...]]]:
    repository = Path(root).resolve()
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repository,
        capture_output=True,
        check=True,
    )
    findings: list[tuple[str, tuple[str, ...]]] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="strict")
        if _excluded(path):
            continue
        source = repository / path
        if not source.is_file() or source.stat().st_size > 4 * 1024 * 1024:
            continue
        raw = source.read_bytes()
        if b"\0" in raw:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        labels = scan_text(text)
        if labels:
            findings.append((path, labels))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    findings = tracked_findings(args.repository)
    if findings:
        for path, labels in findings:
            print(f"{path}: {','.join(labels)}")
        return 1
    print("tracked sensitive-value scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
