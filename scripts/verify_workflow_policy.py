#!/usr/bin/env python3
"""Static fail-closed policy checks for Board 7 GitHub workflow source."""

from __future__ import annotations

import json
import re
from pathlib import Path

_REQUIRED = (
    "ci.yml",
    "deploy-production-worker.yml",
    "publish-production-release.yml",
)
_ALLOWED_ACTIONS = {
    "actions/checkout",
    "actions/setup-python",
    "actions/setup-node",
    "actions/create-github-app-token",
}
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"required workflow is missing: {path.name}")
    return path.read_text(encoding="utf-8")


def _check_action_pins(filename: str, text: str) -> None:
    for reference in _USES.findall(text):
        _require("@" in reference, f"{filename}: action reference is not pinned")
        action, ref = reference.rsplit("@", 1)
        _require(action in _ALLOWED_ACTIONS, f"{filename}: action is not allowlisted: {action}")
        _require(_FULL_SHA.fullmatch(ref) is not None, f"{filename}: action is not full-SHA pinned")


def _check_ci(text: str) -> None:
    _require("permissions:\n  contents: read" in text, "ci.yml must use contents: read")
    _require("${{ secrets." not in text, "ci.yml must not reference GitHub secrets")
    for name in (
        "CLOUDFLARE_API_TOKEN",
        "PRODUCTION_RELEASE_SIGNING_PRIVATE_KEY",
        "PRODUCTION_ACCESS_CLIENT_SECRET",
        "RELEASE_PUBLISHER_APP_PRIVATE_KEY",
    ):
        _require(name not in text, f"ci.yml references production credential {name}")
    _require("pull_request:" in text, "ci.yml must run on pull requests")
    _require("push:" in text, "ci.yml must run on pushes")


def _check_privileged(filename: str, text: str, concurrency_group: str) -> None:
    _require("workflow_dispatch:" in text, f"{filename} must be manually dispatched")
    _require("pull_request_target:" not in text, f"{filename} must not use pull_request_target")
    _require(re.search(r"(?m)^\s{2}(push|pull_request):", text) is None, f"{filename} must not auto-run on push/PR")
    _require(f"group: {concurrency_group}" in text, f"{filename} concurrency group is missing")
    _require("cancel-in-progress: false" in text, f"{filename} must not cancel an in-flight production mutation")
    _require("permissions:\n  contents: read" in text, f"{filename} must use minimal contents: read")
    _require("environment: production" in text, f"{filename} must use production Environment")
    _require("scripts/verify_canonical_main.py" in text, f"{filename} must verify canonical main")
    _require("github.event.inputs.source_sha" in text or "inputs.source_sha" in text, f"{filename} must consume explicit source SHA")


def _check_publish(text: str) -> None:
    lower = text.lower()
    for forbidden in (
        "releases enable",
        "releases resume",
        "rollout_percentage",
        "rollout-percentage",
        "license create",
        "licenses create",
        "/v1/admin/releases/",
    ):
        _require(forbidden not in lower, f"publish workflow contains forbidden state/license mutation: {forbidden}")
    for required in (
        "r2 readiness",
        "immutable github provenance",
        "disabled registration",
        "verify_local_update_artifacts.py",
        "--provenance-target-sha",
        "read-only reconcile",
        "/v1/automation/releases",
    ):
        _require(required in lower, f"publish workflow does not encode {required}")
    marker = "PRODUCTION_RELEASE_SIGNING_PRIVATE_KEY"
    _require(text.count(marker) == 1, "release signing private key must appear exactly once")
    marker_index = text.index(marker)
    _require("uses:" not in text[marker_index:], "no Action step may run after signing-key injection")
    _require("actions/create-github-app-token@" in text[:marker_index], "GitHub App token must be created before signing-key injection")


def verify_workflow_policy(root: str | Path) -> dict[str, bool]:
    repository = Path(root).resolve()
    workflows = repository / ".github" / "workflows"
    result: dict[str, bool] = {}
    texts: dict[str, str] = {}
    for filename in _REQUIRED:
        text = _text(workflows / filename)
        _check_action_pins(filename, text)
        texts[filename] = text
        result[filename] = True
    _check_ci(texts["ci.yml"])
    _check_privileged(
        "deploy-production-worker.yml",
        texts["deploy-production-worker.yml"],
        "production-worker",
    )
    _check_privileged(
        "publish-production-release.yml",
        texts["publish-production-release.yml"],
        "production-release",
    )
    _check_publish(texts["publish-production-release.yml"])
    return result


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = verify_workflow_policy(root)
    print(json.dumps({"ok": True, "workflows": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
