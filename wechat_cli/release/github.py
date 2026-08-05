"""Minimal private GitHub Release client for signed update publication."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

_GITHUB_API_ROOT = "https://api.github.com"
_GITHUB_UPLOAD_HOST = "uploads.github.com"
_GITHUB_API_VERSION = "2026-03-10"


class GitHubTransport(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any] | bytes | None,
        content_type: str | None,
    ) -> tuple[int, Mapping[str, Any]]: ...


@dataclass(frozen=True)
class GitHubReleaseError(Exception):
    code: str
    message: str
    status: int | None = None
    request_id: str | None = None
    retryable: bool = False

    def __str__(self) -> str:
        request = f" (request_id={self.request_id})" if self.request_id else ""
        return f"{self.code}: {self.message}{request}"


@dataclass(frozen=True)
class GitHubRelease:
    release_id: int
    tag_name: str
    upload_url: str
    draft: bool


@dataclass(frozen=True)
class GitHubAsset:
    asset_id: int
    name: str
    size: int
    state: str


class UrllibGitHubTransport:
    def __init__(self, *, timeout_seconds: float = 60.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds

    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any] | bytes | None,
        content_type: str | None,
    ) -> tuple[int, Mapping[str, Any]]:
        request_headers = dict(headers)
        raw_body: bytes | None = None
        if isinstance(body, Mapping):
            raw_body = json.dumps(
                body,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            request_headers["Content-Type"] = content_type or "application/json"
        elif isinstance(body, bytes):
            raw_body = body
            request_headers["Content-Type"] = content_type or "application/octet-stream"
        request = Request(
            url,
            data=raw_body,
            headers=request_headers,
            method=method,
        )
        try:
            response = urlopen(request, timeout=self.timeout_seconds)
        except HTTPError as exc:
            response = exc
        except (URLError, OSError, TimeoutError) as exc:
            raise GitHubReleaseError(
                "GITHUB_SERVICE_UNAVAILABLE",
                str(exc) or "GitHub API unavailable",
                retryable=True,
            ) from exc
        with response:
            raw = response.read(4 * 1024 * 1024 + 1)
            status = int(response.status)
            request_id = response.headers.get("X-GitHub-Request-Id")
        if len(raw) > 4 * 1024 * 1024:
            raise GitHubReleaseError(
                "GITHUB_RESPONSE_TOO_LARGE",
                "GitHub API response was too large",
                status=status,
                request_id=request_id,
                retryable=True,
            )
        if not raw:
            return status, {}
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubReleaseError(
                "GITHUB_INVALID_RESPONSE",
                "GitHub API returned invalid JSON",
                status=status,
                request_id=request_id,
                retryable=status >= 500,
            ) from exc
        if not isinstance(value, Mapping):
            raise GitHubReleaseError(
                "GITHUB_INVALID_RESPONSE",
                "GitHub API response must be an object",
                status=status,
                request_id=request_id,
                retryable=status >= 500,
            )
        result = dict(value)
        if request_id and "request_id" not in result:
            result["request_id"] = request_id
        return status, result


def _required_integer(data: Mapping[str, Any], name: str) -> int:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise GitHubReleaseError(
            "GITHUB_INVALID_RESPONSE",
            f"GitHub response field {name} is invalid",
        )
    return value


def _required_string(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value:
        raise GitHubReleaseError(
            "GITHUB_INVALID_RESPONSE",
            f"GitHub response field {name} is invalid",
        )
    return value


@dataclass
class GitHubReleaseClient:
    repository: str
    token: str = field(repr=False)
    transport: GitHubTransport = field(
        default_factory=UrllibGitHubTransport,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.repository, str) or not self.repository:
            raise ValueError("repository is required")
        parts = self.repository.split("/")
        if len(parts) != 2 or any(
            not part
            or any(
                not (character.isalnum() or character in "_.-")
                for character in part
            )
            for part in parts
        ):
            raise ValueError("repository must use owner/name format")
        if not isinstance(self.token, str) or len(self.token) < 8:
            raise ValueError("GitHub token is missing or invalid")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": _GITHUB_API_VERSION,
            "User-Agent": "wechat-cli-release",
        }

    def _request(
        self,
        method: str,
        url: str,
        body: Mapping[str, Any] | bytes | None = None,
        *,
        content_type: str | None = None,
        expected_statuses: tuple[int, ...] = (200,),
    ) -> Mapping[str, Any]:
        try:
            status, response = self.transport(
                method,
                url,
                self._headers,
                body,
                content_type,
            )
        except GitHubReleaseError:
            raise
        except (OSError, TimeoutError) as exc:
            raise GitHubReleaseError(
                "GITHUB_SERVICE_UNAVAILABLE",
                str(exc) or "GitHub API unavailable",
                retryable=True,
            ) from exc
        if status in expected_statuses:
            return response
        message = response.get("message")
        request_id = response.get("request_id")
        raise GitHubReleaseError(
            "GITHUB_API_ERROR",
            message if isinstance(message, str) and message else f"GitHub API returned HTTP {status}",
            status=status,
            request_id=(str(request_id) if request_id is not None else None),
            retryable=status == 429 or status >= 500,
        )

    def create_release(
        self,
        *,
        tag_name: str,
        name: str,
        body: str,
        target_commitish: str,
        draft: bool = True,
        prerelease: bool = False,
    ) -> GitHubRelease:
        for field_name, value, maximum in (
            ("tag_name", tag_name, 255),
            ("name", name, 255),
            ("target_commitish", target_commitish, 255),
        ):
            if not isinstance(value, str) or not value or len(value) > maximum:
                raise ValueError(f"{field_name} is invalid")
        if not isinstance(body, str) or len(body) > 125_000:
            raise ValueError("release body is invalid")
        response = self._request(
            "POST",
            f"{_GITHUB_API_ROOT}/repos/{self.repository}/releases",
            {
                "tag_name": tag_name,
                "target_commitish": target_commitish,
                "name": name,
                "body": body,
                "draft": bool(draft),
                "prerelease": bool(prerelease),
                "generate_release_notes": False,
            },
            content_type="application/json",
            expected_statuses=(201,),
        )
        draft_value = response.get("draft")
        if not isinstance(draft_value, bool):
            raise GitHubReleaseError(
                "GITHUB_INVALID_RESPONSE",
                "GitHub release response draft field is invalid",
            )
        return GitHubRelease(
            release_id=_required_integer(response, "id"),
            tag_name=_required_string(response, "tag_name"),
            upload_url=_required_string(response, "upload_url"),
            draft=draft_value,
        )

    def _asset_upload_url(self, template: str, filename: str) -> str:
        base = template.split("{", 1)[0]
        parsed = urlparse(base)
        expected_prefix = f"/repos/{self.repository}/releases/"
        if (
            parsed.scheme != "https"
            or parsed.hostname != _GITHUB_UPLOAD_HOST
            or not parsed.path.startswith(expected_prefix)
            or not parsed.path.endswith("/assets")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("GitHub upload URL is not trusted for this repository")
        if not filename or Path(filename).name != filename or len(filename) > 255:
            raise ValueError("asset filename is invalid")
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["name"] = filename
        return urlunparse(
            (
                "https",
                _GITHUB_UPLOAD_HOST,
                parsed.path,
                "",
                urlencode(query),
                "",
            )
        )

    def upload_asset(
        self,
        upload_url: str,
        path: str | Path,
        *,
        content_type: str,
    ) -> GitHubAsset:
        source = Path(path)
        if source.is_symlink() or not source.is_file():
            raise ValueError("release asset must be a regular file")
        if source.stat().st_size <= 0:
            raise ValueError("release asset cannot be empty")
        if not isinstance(content_type, str) or not content_type:
            raise ValueError("content_type is required")
        url = self._asset_upload_url(upload_url, source.name)
        response = self._request(
            "POST",
            url,
            source.read_bytes(),
            content_type=content_type,
            expected_statuses=(201,),
        )
        asset = GitHubAsset(
            asset_id=_required_integer(response, "id"),
            name=_required_string(response, "name"),
            size=_required_integer(response, "size"),
            state=_required_string(response, "state"),
        )
        if asset.state != "uploaded":
            raise GitHubReleaseError(
                "GITHUB_ASSET_UPLOAD_INCOMPLETE",
                f"GitHub asset state is {asset.state!r}",
                retryable=True,
            )
        if asset.name != source.name:
            raise GitHubReleaseError(
                "GITHUB_ASSET_NAME_MISMATCH",
                "GitHub returned another asset name",
            )
        if asset.size != source.stat().st_size:
            raise GitHubReleaseError(
                "GITHUB_ASSET_SIZE_MISMATCH",
                "GitHub returned an unexpected asset size",
            )
        return asset

    def delete_asset(self, asset_id: int) -> None:
        if isinstance(asset_id, bool) or not isinstance(asset_id, int) or asset_id <= 0:
            raise ValueError("asset_id must be positive")
        self._request(
            "DELETE",
            f"{_GITHUB_API_ROOT}/repos/{self.repository}/releases/assets/{asset_id}",
            expected_statuses=(204,),
        )

    def delete_release(self, release_id: int) -> None:
        if (
            isinstance(release_id, bool)
            or not isinstance(release_id, int)
            or release_id <= 0
        ):
            raise ValueError("release_id must be positive")
        self._request(
            "DELETE",
            f"{_GITHUB_API_ROOT}/repos/{self.repository}/releases/{release_id}",
            expected_statuses=(204,),
        )
