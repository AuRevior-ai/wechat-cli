"""Fail-closed Worker deployment preflight. No deployment side effects."""

from __future__ import annotations

import argparse
import json
import runpy
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Collection, Mapping
from urllib.parse import urlparse


_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_POLICY_PATH = _ROOT / "services" / "license-update-worker" / "deployment-policy.json"
_ALLOWED_ENVIRONMENTS = frozenset({"local", "staging", "production"})
_REQUIRED_R2_BINDINGS = frozenset({"DIAGNOSTICS", "RELEASES"})


@dataclass(frozen=True)
class DeploymentPreflightResult:
    environment: str
    worker_name: str
    d1_database_name: str
    r2_bucket_names: tuple[str, ...]
    required_secret_names: tuple[str, ...]

    def to_safe_mapping(self) -> dict[str, object]:
        return {
            "environment": self.environment,
            "worker_name": self.worker_name,
            "d1_database_name": self.d1_database_name,
            "r2_bucket_names": list(self.r2_bucket_names),
            "required_secret_names": list(self.required_secret_names),
        }


def _load_config(path: str | Path) -> dict[str, object]:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Worker configuration must be an existing regular file")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Worker configuration is unreadable") from exc
    if not isinstance(value, dict):
        raise ValueError("Worker configuration root must be an object")
    return value


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _load_policy(path: str | Path) -> Mapping[str, object]:
    try:
        policy = _load_config(path)
    except ValueError as exc:
        raise ValueError("deployment policy is unreadable") from exc
    if policy.get("schema_version") != 2:
        raise ValueError("deployment policy schema is invalid")
    environments = _mapping(policy.get("environments"), "deployment policy environments")
    for environment in _ALLOWED_ENVIRONMENTS:
        entry = _mapping(
            environments.get(environment),
            f"deployment policy {environment} environment",
        )
        worker_name = entry.get("worker_name")
        if not isinstance(worker_name, str) or not worker_name.strip():
            raise ValueError("deployment policy worker name is invalid")
    production = _mapping(environments.get("production"), "production policy")
    if production.get("workers_dev") is not False:
        raise ValueError("deployment policy must disable production workers_dev")
    if production.get("require_custom_route") is not True:
        raise ValueError("deployment policy must require a production custom route")
    bindings = _mapping(policy.get("required_bindings"), "deployment policy bindings")
    d1 = bindings.get("d1")
    r2 = bindings.get("r2")
    if d1 != ["DB"] or r2 != ["DIAGNOSTICS", "RELEASES"]:
        raise ValueError("deployment policy required bindings are invalid")
    for field in (
        "versioned_secret_prefixes",
        "required_secret_names",
        "local_staging_compatibility_secret_names",
    ):
        value = policy.get(field)
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            raise ValueError(f"deployment policy {field} is invalid")
    production_contract = _mapping(
        policy.get("production_contract"),
        "deployment policy production contract",
    )
    required_contract_fields = (
        "public_api_origin_var",
        "admin_origin_var",
        "access_issuer_var",
        "access_jwks_var",
        "human_audiences_var",
        "human_identity_claim_var",
        "human_identity_claim",
        "automation_audiences_var",
        "automation_identity_claim_var",
        "automation_identities_var",
    )
    for field in required_contract_fields:
        value = production_contract.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"deployment policy production contract {field} is invalid")
    if production_contract.get("required_custom_domain_count") != 2:
        raise ValueError("deployment policy production custom-domain count is invalid")
    return policy


def _environment_config(root: Mapping[str, object], environment: str) -> Mapping[str, object]:
    if environment == "local":
        return root
    environments = _mapping(root.get("env"), "Worker environment map")
    if environment not in environments:
        raise ValueError(f"Worker environment {environment!r} is missing")
    return _mapping(environments[environment], f"Worker environment {environment}")


def _validate_worker_names(
    root: Mapping[str, object],
    policy: Mapping[str, object],
) -> None:
    environments = _mapping(root.get("env"), "Worker environment map")
    policy_environments = _mapping(
        policy.get("environments"),
        "deployment policy environments",
    )
    actual = {
        "local": root.get("name"),
        "staging": _mapping(environments.get("staging"), "staging environment").get("name"),
        "production": _mapping(environments.get("production"), "production environment").get("name"),
    }
    for environment in _ALLOWED_ENVIRONMENTS:
        expected = _mapping(
            policy_environments.get(environment),
            f"deployment policy {environment}",
        ).get("worker_name")
        if actual.get(environment) != expected:
            raise ValueError(f"{environment} Worker name does not match deployment policy")
    if len(set(actual.values())) != len(actual):
        raise ValueError("local, staging, and production Worker names must be distinct")


def _contains_placeholder(value: str) -> bool:
    lowered = value.lower()
    return "placeholder" in lowered or "replace" in lowered


def _bindings(
    environment: str,
    config: Mapping[str, object],
    *,
    reject_placeholders: bool = True,
) -> tuple[str, str, dict[str, str]]:
    vars_value = _mapping(config.get("vars"), f"{environment} vars")
    if vars_value.get("ENVIRONMENT") != environment:
        raise ValueError(f"{environment} ENVIRONMENT variable does not match target")

    d1_value = config.get("d1_databases")
    if not isinstance(d1_value, list):
        raise ValueError(f"{environment} D1 bindings are missing")
    db_rows = [
        row
        for row in d1_value
        if isinstance(row, Mapping) and row.get("binding") == "DB"
    ]
    if len(db_rows) != 1:
        raise ValueError(f"{environment} requires exactly one DB binding")
    database_name = str(db_rows[0].get("database_name", "")).strip()
    database_id = str(db_rows[0].get("database_id", "")).strip()
    if not database_name or not database_id:
        raise ValueError(f"{environment} DB binding is incomplete")

    r2_value = config.get("r2_buckets")
    if not isinstance(r2_value, list):
        raise ValueError(f"{environment} R2 bindings are missing")
    buckets: dict[str, str] = {}
    for row in r2_value:
        if not isinstance(row, Mapping):
            continue
        binding = str(row.get("binding", "")).strip()
        bucket_name = str(row.get("bucket_name", "")).strip()
        if binding in _REQUIRED_R2_BINDINGS:
            if binding in buckets:
                raise ValueError(f"{environment} has duplicate R2 binding {binding}")
            buckets[binding] = bucket_name
    if set(buckets) != set(_REQUIRED_R2_BINDINGS) or any(not value for value in buckets.values()):
        raise ValueError(f"{environment} requires DIAGNOSTICS and RELEASES R2 bindings")

    if environment in {"staging", "production"} and reject_placeholders:
        if _contains_placeholder(database_id):
            raise ValueError(f"{environment} D1 binding contains a placeholder")
        if any(_contains_placeholder(value) for value in buckets.values()):
            raise ValueError(f"{environment} R2 binding contains a placeholder")
    return database_name, database_id, buckets


def _validate_environment_isolation(
    root: Mapping[str, object],
    target_environment: str,
) -> None:
    staging = _environment_config(root, "staging")
    production = _environment_config(root, "production")
    staging_name, staging_id, staging_buckets = _bindings(
        "staging",
        staging,
        reject_placeholders=target_environment in {"staging", "production"},
    )
    production_name, production_id, production_buckets = _bindings(
        "production",
        production,
        reject_placeholders=target_environment == "production",
    )
    if staging_name == production_name:
        raise ValueError("staging/production D1 database-name collision")
    if (
        not _contains_placeholder(staging_id)
        and not _contains_placeholder(production_id)
        and staging_id == production_id
    ):
        raise ValueError("staging/production D1 resource collision")
    for binding in _REQUIRED_R2_BINDINGS:
        if staging_buckets[binding] == production_buckets[binding]:
            raise ValueError(f"staging/production R2 resource collision for {binding}")


def _validate_production_ingress(config: Mapping[str, object]) -> None:
    if config.get("workers_dev") is not False:
        raise ValueError("production workers_dev must be false")
    routes = config.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("production custom route is required")


def _exact_https_origin(value: object, label: str) -> tuple[str, str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is missing")
    raw = value.strip()
    if _contains_placeholder(raw):
        raise ValueError(f"{label} contains a placeholder")
    parsed = urlparse(raw)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.hostname.lower().endswith(".workers.dev")
    ):
        raise ValueError(f"{label} is invalid")
    return raw.rstrip("/"), parsed.hostname.lower()


def _csv_values(value: object, label: str, *, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise ValueError(f"{label} is missing")
    values = tuple(item.strip() for item in value.split(",") if item.strip())
    if (
        not values
        or len(values) > maximum
        or len(set(values)) != len(values)
        or any(_contains_placeholder(item) for item in values)
    ):
        raise ValueError(f"{label} is invalid")
    return values


def _validate_production_access_boundary(
    config: Mapping[str, object],
    policy: Mapping[str, object],
) -> None:
    vars_value = _mapping(config.get("vars"), "production vars")
    contract = _mapping(policy.get("production_contract"), "production contract")

    def variable(field: str) -> tuple[str, object]:
        name = str(contract[field])
        return name, vars_value.get(name)

    api_name, api_raw = variable("public_api_origin_var")
    admin_name, admin_raw = variable("admin_origin_var")
    api_origin, api_host = _exact_https_origin(api_raw, api_name)
    admin_origin, admin_host = _exact_https_origin(admin_raw, admin_name)
    if api_origin == admin_origin or api_host == admin_host:
        raise ValueError("production API and Admin origins must be distinct")
    if "staging" in api_host or "staging" in admin_host:
        raise ValueError("production configuration contains a staging hostname")

    issuer_name, issuer_raw = variable("access_issuer_var")
    jwks_name, jwks_raw = variable("access_jwks_var")
    issuer_origin, issuer_host = _exact_https_origin(issuer_raw, issuer_name)
    if not issuer_host.endswith(".cloudflareaccess.com"):
        raise ValueError("production Access issuer is invalid")
    if not isinstance(jwks_raw, str) or not jwks_raw.strip():
        raise ValueError(f"{jwks_name} is missing")
    jwks = urlparse(jwks_raw.strip())
    if (
        jwks.scheme != "https"
        or jwks.username
        or jwks.password
        or jwks.netloc.lower() != urlparse(issuer_origin).netloc.lower()
        or jwks.path != "/cdn-cgi/access/certs"
        or jwks.query
        or jwks.fragment
    ):
        raise ValueError("production Access JWKS configuration is invalid")

    human_aud_name, human_aud_raw = variable("human_audiences_var")
    automation_aud_name, automation_aud_raw = variable("automation_audiences_var")
    human_audiences = set(_csv_values(human_aud_raw, human_aud_name, maximum=8))
    automation_audiences = set(
        _csv_values(automation_aud_raw, automation_aud_name, maximum=8)
    )
    if human_audiences & automation_audiences:
        raise ValueError("production human and automation Access audiences must be distinct")

    human_claim_name, human_claim_raw = variable("human_identity_claim_var")
    if human_claim_raw != contract.get("human_identity_claim"):
        raise ValueError(f"production {human_claim_name} is invalid")
    automation_claim_name, automation_claim_raw = variable("automation_identity_claim_var")
    if (
        not isinstance(automation_claim_raw, str)
        or not automation_claim_raw.strip()
        or _contains_placeholder(automation_claim_raw)
        or automation_claim_raw == human_claim_raw
    ):
        raise ValueError(f"production {automation_claim_name} is invalid")
    identities_name, identities_raw = variable("automation_identities_var")
    _csv_values(identities_raw, identities_name, maximum=32)

    routes = config.get("routes")
    if not isinstance(routes, list):
        raise ValueError("production custom-domain routes are missing")
    exact_hosts: list[str] = []
    for route in routes:
        if not isinstance(route, Mapping) or route.get("custom_domain") is not True:
            raise ValueError("production routes must use exact custom domains")
        pattern = route.get("pattern")
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError("production custom-domain route is invalid")
        exact_hosts.append(pattern.strip().lower())
    required_count = int(contract["required_custom_domain_count"])
    if len(exact_hosts) != required_count or set(exact_hosts) != {api_host, admin_host}:
        raise ValueError("production custom-domain route set must match API and Admin origins")


def _validate_staging_access_boundary(config: Mapping[str, object]) -> None:
    vars_value = _mapping(config.get("vars"), "staging vars")
    required = (
        "ACCESS_JWT_ISSUER",
        "ACCESS_JWKS_URL",
        "ACCESS_AUDIENCES",
        "ACCESS_IDENTITY_CLAIM",
        "ACCESS_ADMIN_ORIGIN",
    )
    values: dict[str, str] = {}
    for name in required:
        value = vars_value.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"staging Access configuration is missing {name}")
        values[name] = value.strip()

    issuer = urlparse(values["ACCESS_JWT_ISSUER"])
    if (
        issuer.scheme != "https"
        or not issuer.hostname
        or issuer.username
        or issuer.password
        or issuer.path not in {"", "/"}
        or issuer.query
        or issuer.fragment
        or not issuer.hostname.lower().endswith(".cloudflareaccess.com")
    ):
        raise ValueError("staging Access issuer is invalid")

    jwks = urlparse(values["ACCESS_JWKS_URL"])
    if (
        jwks.scheme != "https"
        or jwks.netloc.lower() != issuer.netloc.lower()
        or jwks.path != "/cdn-cgi/access/certs"
        or jwks.query
        or jwks.fragment
    ):
        raise ValueError("staging Access JWKS configuration is invalid")

    audiences = [item.strip() for item in values["ACCESS_AUDIENCES"].split(",") if item.strip()]
    if not audiences or len(audiences) > 8 or len(set(audiences)) != len(audiences):
        raise ValueError("staging Access audience configuration is invalid")
    if values["ACCESS_IDENTITY_CLAIM"] != "email":
        raise ValueError("staging Access identity claim must be email")

    admin_origin = urlparse(values["ACCESS_ADMIN_ORIGIN"])
    if (
        admin_origin.scheme != "https"
        or not admin_origin.hostname
        or admin_origin.username
        or admin_origin.password
        or admin_origin.path not in {"", "/"}
        or admin_origin.query
        or admin_origin.fragment
        or admin_origin.hostname.lower().endswith(".workers.dev")
    ):
        raise ValueError("staging Access admin origin is invalid")

    routes = config.get("routes")
    if not isinstance(routes, list):
        raise ValueError("staging Access custom-domain route is required")
    expected_host = admin_origin.hostname.lower()
    matching = [
        route
        for route in routes
        if isinstance(route, Mapping)
        and route.get("custom_domain") is True
        and str(route.get("pattern", "")).strip().lower() == expected_host
    ]
    if len(matching) != 1:
        raise ValueError("staging Access custom-domain route does not match admin origin")


def _selector_versions(vars_value: Mapping[str, object], prefix: str) -> tuple[int, ...]:
    current_raw = str(vars_value.get(f"{prefix}_CURRENT_VERSION", "")).strip()
    readable_raw = str(vars_value.get(f"{prefix}_READABLE_VERSIONS", "")).strip()
    if not current_raw.isdigit() or not readable_raw:
        raise ValueError(f"{prefix} version selector is missing or invalid")
    current = int(current_raw)
    parts = [item.strip() for item in readable_raw.split(",")]
    if (
        current < 1
        or current > 99
        or not parts
        or len(parts) > 8
        or any(not item.isdigit() for item in parts)
    ):
        raise ValueError(f"{prefix} version selector is invalid")
    readable = tuple(int(item) for item in parts)
    if (
        any(version < 1 or version > 99 for version in readable)
        or len(set(readable)) != len(readable)
        or current not in readable
    ):
        raise ValueError(f"{prefix} version selector is invalid")
    return tuple(sorted(readable))


def _required_secret_names(
    environment: str,
    config: Mapping[str, object],
    policy: Mapping[str, object],
) -> tuple[str, ...]:
    vars_value = _mapping(config.get("vars"), f"{environment} vars")
    prefixes = policy.get("versioned_secret_prefixes")
    required_names = policy.get("required_secret_names")
    compatibility_names = policy.get("local_staging_compatibility_secret_names")
    if not isinstance(prefixes, list) or not isinstance(required_names, list):
        raise ValueError("deployment policy secret declarations are invalid")
    if not isinstance(compatibility_names, list):
        raise ValueError("deployment policy compatibility secret declarations are invalid")
    names: set[str] = {str(name) for name in required_names}
    for prefix_value in prefixes:
        prefix = str(prefix_value)
        for version in _selector_versions(vars_value, prefix):
            names.add(f"{prefix}_V{version}")
    contact_version = str(vars_value.get("CONTACT_ENCRYPTION_KEY_VERSION", "")).strip()
    if not contact_version.isdigit() or not 1 <= int(contact_version) <= 99:
        raise ValueError("CONTACT_ENCRYPTION_KEY_VERSION is invalid")
    names.add(f"CONTACT_ENCRYPTION_KEY_V{int(contact_version)}")
    if environment in {"local", "staging"}:
        names.update(str(name) for name in compatibility_names)
    return tuple(sorted(names))


def _validate_production_route_origin(
    config: Mapping[str, object],
    api_origin: str,
) -> None:
    hostname = (urlparse(api_origin).hostname or "").lower()
    if not hostname:
        raise ValueError("production API origin hostname is invalid")
    routes = config.get("routes")
    patterns: list[str] = []
    if isinstance(routes, list):
        for route in routes:
            if isinstance(route, str):
                patterns.append(route)
            elif isinstance(route, Mapping) and isinstance(route.get("pattern"), str):
                patterns.append(str(route["pattern"]))
    route_hosts = {
        pattern.strip().lower().removeprefix("https://").removeprefix("http://").split("/", 1)[0]
        for pattern in patterns
        if pattern.strip()
    }
    if hostname not in route_hosts:
        raise ValueError("production custom route does not match embedded API origin")


def _validate_trust_profile(
    environment: str,
    trust_profile_path: str | Path | None,
    api_origin: str | None,
) -> None:
    if environment == "local" and trust_profile_path is None and api_origin is None:
        return
    if trust_profile_path is None:
        raise ValueError(f"{environment} deployment trust profile is required")
    if not isinstance(api_origin, str) or not api_origin.strip():
        raise ValueError(f"{environment} API origin is required for trust preflight")
    namespace = runpy.run_path(
        str(_ROOT / "wechat_cli" / "launcher" / "trust_profile.py")
    )
    profile_type = namespace["DeploymentTrustProfile"]
    profile = profile_type.load(trust_profile_path)
    if profile.environment != environment:
        raise ValueError("deployment trust profile environment does not match target")
    expected_origin = profile.api_base_url.rstrip("/")
    actual_origin = api_origin.strip().rstrip("/")
    if actual_origin != expected_origin:
        raise ValueError("deployment API origin does not match embedded trust profile")


def preflight_worker_deployment(
    config_path: str | Path,
    *,
    environment: str,
    policy_path: str | Path = _DEFAULT_POLICY_PATH,
    trust_profile_path: str | Path | None = None,
    api_origin: str | None = None,
    declared_secret_names: Collection[str] = (),
) -> DeploymentPreflightResult:
    if environment not in _ALLOWED_ENVIRONMENTS:
        raise ValueError("deployment environment must be explicitly local, staging, or production")
    root = _load_config(config_path)
    policy = _load_policy(policy_path)
    _validate_worker_names(root, policy)
    _validate_environment_isolation(root, environment)
    config = _environment_config(root, environment)
    database_name, _database_id, buckets = _bindings(environment, config)
    if environment == "staging":
        _validate_staging_access_boundary(config)
    if environment == "production":
        _validate_production_ingress(config)
        _validate_production_access_boundary(config, policy)
    _validate_trust_profile(environment, trust_profile_path, api_origin)
    if environment == "production":
        configured_api_origin = str(
            _mapping(config.get("vars"), "production vars").get("PUBLIC_API_ORIGIN", "")
        ).rstrip("/")
        if configured_api_origin != str(api_origin).strip().rstrip("/"):
            raise ValueError("production API origin does not match PUBLIC_API_ORIGIN")
        _validate_production_route_origin(config, str(api_origin))
    required_secrets = _required_secret_names(environment, config, policy)
    declared = {
        value.strip()
        for value in declared_secret_names
        if isinstance(value, str) and value.strip()
    }
    missing = tuple(name for name in required_secrets if name not in declared)
    if missing:
        raise ValueError("missing required secret names: " + ", ".join(missing))
    worker_name = str(config.get("name", "")).strip()
    return DeploymentPreflightResult(
        environment=environment,
        worker_name=worker_name,
        d1_database_name=database_name,
        r2_bucket_names=tuple(sorted(buckets.values())),
        required_secret_names=required_secrets,
    )


def _validated_external_secrets_file(path: str | Path) -> Path:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("deployment secrets file must be an existing non-symlink regular file")
    resolved = source.resolve()
    try:
        resolved.relative_to(_ROOT.resolve())
    except ValueError:
        return resolved
    raise ValueError("deployment secrets file must remain outside the repository")


def deploy_staging_worker(
    config_path: str | Path,
    *,
    environment: str,
    policy_path: str | Path = _DEFAULT_POLICY_PATH,
    trust_profile_path: str | Path | None = None,
    api_origin: str | None = None,
    declared_secret_names: Collection[str] = (),
    secrets_file: str | Path | None = None,
    runner: Callable[..., object] = subprocess.run,
    emit: Callable[[str], object] = print,
) -> DeploymentPreflightResult:
    if environment != "staging":
        raise ValueError("deployment action is restricted to staging")
    result = preflight_worker_deployment(
        config_path,
        environment=environment,
        policy_path=policy_path,
        trust_profile_path=trust_profile_path,
        api_origin=api_origin,
        declared_secret_names=declared_secret_names,
    )
    emit(json.dumps(result.to_safe_mapping(), sort_keys=True))
    source = Path(config_path).resolve()
    npx = shutil.which("npx")
    if npx is None:
        raise RuntimeError("npx executable is unavailable")
    command = [
        npx,
        "wrangler",
        "deploy",
        "--env",
        "staging",
        "--config",
        str(source),
    ]
    if secrets_file is not None:
        command.extend(
            ["--secrets-file", str(_validated_external_secrets_file(secrets_file))]
        )
    runner(
        command,
        cwd=source.parent,
        check=True,
    )
    return result


def deploy_production_worker(
    config_path: str | Path,
    *,
    environment: str,
    source_sha: str,
    policy_path: str | Path = _DEFAULT_POLICY_PATH,
    trust_profile_path: str | Path | None = None,
    api_origin: str | None = None,
    declared_secret_names: Collection[str] = (),
    secrets_file: str | Path | None = None,
    runner: Callable[..., object] = subprocess.run,
    emit: Callable[[str], object] = print,
) -> DeploymentPreflightResult:
    if environment != "production":
        raise ValueError("production deployment action requires environment=production")
    if (
        not isinstance(source_sha, str)
        or len(source_sha) != 40
        or any(character not in "0123456789abcdef" for character in source_sha)
    ):
        raise ValueError("production deployment source SHA must be 40 lowercase hex characters")
    result = preflight_worker_deployment(
        config_path,
        environment=environment,
        policy_path=policy_path,
        trust_profile_path=trust_profile_path,
        api_origin=api_origin,
        declared_secret_names=declared_secret_names,
    )
    validated_secrets_file = (
        None
        if secrets_file is None
        else _validated_external_secrets_file(secrets_file)
    )
    safe = result.to_safe_mapping()
    safe["source_sha"] = source_sha
    emit(json.dumps(safe, sort_keys=True))
    source = Path(config_path).resolve()
    npx = shutil.which("npx")
    if npx is None:
        raise RuntimeError("npx executable is unavailable")
    command = [
        npx,
        "wrangler",
        "deploy",
        "--env",
        "production",
        "--config",
        str(source),
    ]
    if validated_secrets_file is not None:
        command.extend(["--secrets-file", str(validated_secrets_file)])
    runner(command, cwd=source.parent, check=True)
    return result


def _add_target_arguments(
    command: argparse.ArgumentParser,
    *,
    environment_choices: tuple[str, ...],
) -> None:
    command.add_argument(
        "--config",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "services"
            / "license-update-worker"
            / "wrangler.jsonc"
        ),
        help="Wrangler source configuration to validate.",
    )
    command.add_argument(
        "--environment",
        required=True,
        choices=environment_choices,
        help="Explicit target environment.",
    )
    command.add_argument(
        "--trust-profile",
        type=Path,
        help="Deployment trust profile used for staging/production readiness checks.",
    )
    command.add_argument(
        "--api-origin",
        help="Exact API origin expected by the embedded deployment trust profile.",
    )
    command.add_argument(
        "--secret-name",
        action="append",
        default=[],
        help="Declared Secret name. Values are never accepted or read.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed Worker deployment preflight and staging-only deployment."
    )
    subcommands = parser.add_subparsers(dest="action", required=True)
    preflight = subcommands.add_parser(
        "preflight",
        help="Validate a target environment without invoking Wrangler.",
    )
    _add_target_arguments(
        preflight,
        environment_choices=tuple(sorted(_ALLOWED_ENVIRONMENTS)),
    )
    deploy = subcommands.add_parser(
        "deploy",
        help="Deploy only the staging Worker after a successful preflight.",
    )
    _add_target_arguments(deploy, environment_choices=("staging",))
    deploy.add_argument(
        "--secrets-file",
        type=Path,
        help=(
            "Optional repo-external Wrangler secrets file for an atomic staging deploy. "
            "The wrapper validates only the path and never reads or prints Secret values."
        ),
    )
    args = parser.parse_args(argv)
    try:
        if args.action == "deploy":
            deploy_staging_worker(
                args.config,
                environment=args.environment,
                trust_profile_path=args.trust_profile,
                api_origin=args.api_origin,
                declared_secret_names=args.secret_name,
                secrets_file=args.secrets_file,
            )
            return 0
        result = preflight_worker_deployment(
            args.config,
            environment=args.environment,
            trust_profile_path=args.trust_profile,
            api_origin=args.api_origin,
            declared_secret_names=args.secret_name,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result.to_safe_mapping(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
