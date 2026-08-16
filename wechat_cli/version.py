"""Shared product and version metadata.

Keep runtime code on this module instead of repeating version literals across
commands, health responses, launcher requests, and package metadata checks.
"""

from __future__ import annotations

import os

PRODUCT = "wechat-cli-web"
APP_VERSION = "0.6.1-canary.1"
LAUNCHER_VERSION = "0.2.0"
UPDATE_SCHEMA_VERSION = 1
API_VERSION = "v1"
PLATFORM = "windows"
ARCHITECTURE = "x86_64"
DEFAULT_BUILD_ID = "dev"
BUILD_ID = os.environ.get("WECHAT_CLI_BUILD_ID", DEFAULT_BUILD_ID)


def production_build_id(source_sha: str) -> str:
    """Derive the production build label from one trusted full Git commit SHA."""
    if (
        not isinstance(source_sha, str)
        or len(source_sha) != 40
        or any(character not in "0123456789abcdef" for character in source_sha)
    ):
        raise ValueError("production source SHA must be 40 lowercase hexadecimal characters")
    return f"prod-060-{source_sha[:12]}"
