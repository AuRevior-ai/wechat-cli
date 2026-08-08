"""Shared product and version metadata.

Keep runtime code on this module instead of repeating version literals across
commands, health responses, launcher requests, and package metadata checks.
"""

from __future__ import annotations

import os

PRODUCT = "wechat-cli-web"
APP_VERSION = "0.5.1"
LAUNCHER_VERSION = "0.1.0"
UPDATE_SCHEMA_VERSION = 1
API_VERSION = "v1"
PLATFORM = "windows"
ARCHITECTURE = "x86_64"
DEFAULT_BUILD_ID = "staging-051-20260808.1"
BUILD_ID = os.environ.get("WECHAT_CLI_BUILD_ID", DEFAULT_BUILD_ID)
