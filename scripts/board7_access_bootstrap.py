#!/usr/bin/env python3
"""Bounded Cloudflare Access provisioning for Board 7.

G3 creates exactly two production Access application identities and exactly one
human allow policy. The automation application intentionally remains deny by
default until B7-G4 creates the exact service token and Service Auth policy.

API tokens are accepted only in process memory and are never printed or stored.
"""

from __future__ import annotations

import argparse
import getpass
import json
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ACCOUNT_ID = "2040a134dbf533fd538deae668556226"
API_BASE = "https://api.cloudflare.com/client/v4"

HUMAN_APP_NAME = "wechat-cli-production-human-admin"
HUMAN_APP_DOMAIN = "wechat-cli-admin.aurevior-devspace.com/v1/admin/login/start"
HUMAN_POLICY_NAME = "wechat-cli-production-human-admin-allow"

AUTOMATION_APP_NAME = "wechat-cli-production-release-automation"
AUTOMATION_APP_DOMAIN = "wechat-cli-admin.aurevior-devspace.com/v1/automation/*"

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AccessProvisionError(RuntimeError):
    pass


def _normalize_email(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _EMAIL_RE.fullmatch(normalized):
        raise ValueError("human Access identity must be one valid email address")
    return normalized


def build_g3_plan(human_email: str) -> dict[str, Any]:
    email = _normalize_email(human_email)
    return {
        "account_id": ACCOUNT_ID,
        "human_app": {
            "name": HUMAN_APP_NAME,
            "domain": HUMAN_APP_DOMAIN,
            "type": "self_hosted",
            "session_duration": "30m",
            "app_launcher_visible": False,
            "allow_authenticate_via_warp": False,
        },
        "human_policy": {
            "name": HUMAN_POLICY_NAME,
            "decision": "allow",
            "include": [{"email": {"email": email}}],
        },
        "automation_app": {
            "name": AUTOMATION_APP_NAME,
            "domain": AUTOMATION_APP_DOMAIN,
            "type": "self_hosted",
            "session_duration": "30m",
            "app_launcher_visible": False,
            "allow_authenticate_via_warp": False,
            "service_auth_401_redirect": True,
        },
    }


def _api_error_message(status: int, payload: object) -> str:
    codes: list[str] = []
    if isinstance(payload, Mapping):
        errors = payload.get("errors")
        if isinstance(errors, list):
            for item in errors[:3]:
                if isinstance(item, Mapping):
                    code = item.get("code")
                    message = item.get("message")
                    if code is not None:
                        codes.append(str(code))
                    elif isinstance(message, str) and message:
                        codes.append("api_error")
    suffix = ",".join(codes) if codes else "unknown"
    return f"Cloudflare Access API request failed: HTTP {status}; codes={suffix}"


def request_json(
    method: str,
    path: str,
    *,
    token: str,
    body: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    if not token or not token.strip():
        raise ValueError("Cloudflare API token is required")
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        API_BASE + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "wechat-cli-board7-access-bootstrap/1",
        },
    )
    try:
        with urlopen(request, timeout=30.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = None
        raise AccessProvisionError(_api_error_message(int(exc.code), payload)) from exc
    except URLError as exc:
        raise AccessProvisionError("Cloudflare Access API request failed before a response") from exc
    if not isinstance(payload, dict):
        raise AccessProvisionError("Cloudflare Access API returned a non-object response")
    return payload


def _result(payload: Mapping[str, object], label: str) -> object:
    if payload.get("success") is not True:
        raise AccessProvisionError(f"Cloudflare Access {label} did not report success")
    if "result" not in payload:
        raise AccessProvisionError(f"Cloudflare Access {label} omitted result")
    return payload["result"]


def _created_app(
    payload: Mapping[str, object],
    *,
    expected_name: str,
    expected_domain: str,
) -> tuple[str, str]:
    raw = _result(payload, "application create")
    if not isinstance(raw, Mapping):
        raise AccessProvisionError("Cloudflare Access application result is invalid")
    app_id = raw.get("id")
    audience = raw.get("aud")
    if (
        not isinstance(app_id, str)
        or not app_id
        or not isinstance(audience, str)
        or not audience
        or raw.get("name") != expected_name
        or raw.get("domain") != expected_domain
        or raw.get("type") != "self_hosted"
    ):
        raise AccessProvisionError("Cloudflare Access application identity drifted")
    return app_id, audience


def _created_policy_id(payload: Mapping[str, object]) -> str:
    raw = _result(payload, "human policy create")
    if not isinstance(raw, Mapping) or not isinstance(raw.get("id"), str) or not raw["id"]:
        raise AccessProvisionError("Cloudflare Access human policy result is invalid")
    return str(raw["id"])


def execute_g3(
    *,
    api_token: str,
    human_email: str,
    requester: Callable[..., dict[str, Any]] = request_json,
) -> dict[str, str]:
    plan = build_g3_plan(human_email)
    apps_path = f"/accounts/{ACCOUNT_ID}/access/apps"

    existing_payload = requester("GET", apps_path, token=api_token)
    existing = _result(existing_payload, "application inventory")
    if not isinstance(existing, list):
        raise AccessProvisionError("Cloudflare Access application inventory is invalid")
    target_names = {HUMAN_APP_NAME, AUTOMATION_APP_NAME}
    target_domains = {HUMAN_APP_DOMAIN, AUTOMATION_APP_DOMAIN}
    for item in existing:
        if not isinstance(item, Mapping):
            continue
        if item.get("name") in target_names or item.get("domain") in target_domains:
            raise AccessProvisionError("exact Board 7 Access application target already exists")

    human_payload = requester(
        "POST",
        apps_path,
        token=api_token,
        body=plan["human_app"],
    )
    human_app_id, human_audience = _created_app(
        human_payload,
        expected_name=HUMAN_APP_NAME,
        expected_domain=HUMAN_APP_DOMAIN,
    )

    policy_payload = requester(
        "POST",
        f"{apps_path}/{human_app_id}/policies",
        token=api_token,
        body=plan["human_policy"],
    )
    human_policy_id = _created_policy_id(policy_payload)

    automation_payload = requester(
        "POST",
        apps_path,
        token=api_token,
        body=plan["automation_app"],
    )
    automation_app_id, automation_audience = _created_app(
        automation_payload,
        expected_name=AUTOMATION_APP_NAME,
        expected_domain=AUTOMATION_APP_DOMAIN,
    )

    if human_audience == automation_audience:
        raise AccessProvisionError("human and automation Access audiences unexpectedly match")

    return {
        "human_app_id": human_app_id,
        "human_audience": human_audience,
        "human_policy_id": human_policy_id,
        "automation_app_id": automation_app_id,
        "automation_audience": automation_audience,
        "automation_policy_state": "deny_by_default_until_g4",
    }


def _safe_plan() -> dict[str, object]:
    return {
        "account_id": ACCOUNT_ID,
        "human_app": {"name": HUMAN_APP_NAME, "domain": HUMAN_APP_DOMAIN, "session_duration": "30m"},
        "human_policy": "single exact email supplied interactively",
        "automation_app": {"name": AUTOMATION_APP_NAME, "domain": AUTOMATION_APP_DOMAIN},
        "automation_policy": "none in G3; deny by default until exact G4 service token exists",
        "service_token_write": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Provision the bounded Board 7 G3 Cloudflare Access identities."
    )
    parser.add_argument("g3", nargs="?", default="g3", choices=("g3",))
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the exact G3 Access writes. Without this flag only a safe plan is emitted.",
    )
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps(_safe_plan(), ensure_ascii=False, sort_keys=True))
        return 0

    human_email = input("Accepted production human Access email: ").strip()
    api_token = getpass.getpass("Cloudflare API token (not echoed): ")
    result = execute_g3(api_token=api_token, human_email=human_email)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
