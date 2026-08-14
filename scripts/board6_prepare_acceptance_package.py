#!/usr/bin/env python3
"""Prepare the scoped Board 6 G5 disposable acceptance update package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

try:
    from scripts.packaging_paths import assert_outside_repository
except ModuleNotFoundError:  # Direct execution: python scripts/board6_prepare_acceptance_package.py
    from packaging_paths import assert_outside_repository


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_VERSION = "0.5.2-board6g5.1"
CANDIDATE_BUILD_ID = "staging-051-20260808.1"
FROZEN_EXE_SIZE = 14483951
FROZEN_EXE_SHA256 = "dbbdf8ec70ddcf8d36145f099b0cb4ce3292c61e205c3ac7ae4db01fbc8907d1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_acceptance_package(
    known_good_exe: str | Path,
    output: str | Path,
    *,
    candidate_version: str = CANDIDATE_VERSION,
    build_id: str = CANDIDATE_BUILD_ID,
) -> Path:
    source = Path(known_good_exe)
    if source.is_symlink() or not source.is_file():
        raise ValueError("known-good executable must be an existing regular file")
    if source.stat().st_size != FROZEN_EXE_SIZE or sha256_file(source) != FROZEN_EXE_SHA256:
        raise ValueError("known-good executable does not match the frozen Board 5 accepted 0.5.1 bytes")
    if candidate_version != CANDIDATE_VERSION:
        raise ValueError("candidate version is outside the approved Board 6 G5 acceptance matrix")
    if build_id != CANDIDATE_BUILD_ID:
        raise ValueError("candidate build ID is outside the approved Board 6 G5 acceptance matrix")

    destination = assert_outside_repository(Path(output), repository_root=ROOT)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "product": "wechat-cli-web",
        "version": candidate_version,
        "platform": "windows",
        "architecture": "x86_64",
        "entrypoint": "wechat-cli.exe",
        "build_id": build_id,
    }
    with tempfile.TemporaryDirectory(prefix="board6-g5-acceptance-") as tmp:
        assembly = Path(tmp)
        copied = assembly / "wechat-cli.exe"
        manifest_path = assembly / "app-manifest.json"
        shutil.copy2(source, copied)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(copied, "wechat-cli.exe")
            archive.write(manifest_path, "app-manifest.json")
    return destination


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare the Board 6 G5 disposable acceptance package.")
    parser.add_argument("--known-good-exe", type=Path, required=True)
    parser.add_argument("--candidate-version", default=CANDIDATE_VERSION)
    parser.add_argument("--build-id", default=CANDIDATE_BUILD_ID)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = prepare_acceptance_package(
            args.known_good_exe,
            args.output,
            candidate_version=args.candidate_version,
            build_id=args.build_id,
        )
    except (ValueError, FileExistsError, OSError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": type(exc).__name__}, sort_keys=True))
        else:
            print(f"[-] {exc}")
        return 2

    summary = {
        "ok": True,
        "candidate_version": CANDIDATE_VERSION,
        "build_id": CANDIDATE_BUILD_ID,
        "package_path": str(output),
        "package_size": output.stat().st_size,
        "package_sha256": sha256_file(output),
        "source_exe_size": FROZEN_EXE_SIZE,
        "source_exe_sha256": FROZEN_EXE_SHA256,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
