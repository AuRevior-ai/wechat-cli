"""Windows Authenticode verification boundary."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal


@dataclass(frozen=True)
class AuthenticodeSignature:
    status: str
    subject: str | None
    thumbprint: str | None
    issuer: str | None = None
    certificate_valid_from: str | None = None
    certificate_valid_to: str | None = None
    # `present` means Get-AuthenticodeSignature exposed a TimeStamperCertificate.
    # It does not independently assert cryptographic timestamp validation.
    timestamp_status: Literal["absent", "present"] = "absent"
    timestamp_subject: str | None = None
    timestamp_issuer: str | None = None
    timestamp_valid_from: str | None = None
    timestamp_valid_to: str | None = None


@dataclass(frozen=True)
class AuthenticodePolicy:
    required: bool
    expected_subject: str | None = None
    expected_thumbprints: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        normalized = frozenset(
            value.replace(" ", "").upper()
            for value in self.expected_thumbprints
            if isinstance(value, str) and value.replace(" ", "")
        )
        if len(normalized) != len(self.expected_thumbprints):
            raise ValueError("Authenticode thumbprint policy is invalid")
        object.__setattr__(self, "expected_thumbprints", normalized)


def _windows_powershell_paths() -> tuple[Path, Path]:
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if not system_root:
        raise ValueError("Windows system root is unavailable")
    root = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0"
    return root / "powershell.exe", root / "Modules"


def inspect_windows_authenticode(
    path: str | Path,
    *,
    runner=None,
) -> AuthenticodeSignature:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Authenticode target must be an existing regular file")
    execute = runner or subprocess.run
    powershell, module_root = _windows_powershell_paths()
    child_env = os.environ.copy()
    child_env["PSModulePath"] = str(module_root)
    child_env["WECHAT_CLI_AUTHENTICODE_TARGET"] = str(source)
    command = [
        str(powershell),
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "$ErrorActionPreference='Stop';"
            "Import-Module Microsoft.PowerShell.Security -ErrorAction Stop;"
            "$s=Get-AuthenticodeSignature -LiteralPath $env:WECHAT_CLI_AUTHENTICODE_TARGET;"
            "[pscustomobject]@{"
            "Status=$s.Status.ToString();"
            "Subject=if($s.SignerCertificate){$s.SignerCertificate.Subject}else{$null};"
            "Issuer=if($s.SignerCertificate){$s.SignerCertificate.Issuer}else{$null};"
            "NotBefore=if($s.SignerCertificate){$s.SignerCertificate.NotBefore.ToUniversalTime().ToString('o')}else{$null};"
            "NotAfter=if($s.SignerCertificate){$s.SignerCertificate.NotAfter.ToUniversalTime().ToString('o')}else{$null};"
            "Thumbprint=if($s.SignerCertificate){$s.SignerCertificate.Thumbprint}else{$null};"
            "TimestampPresent=[bool]$s.TimeStamperCertificate;"
            "TimestampSubject=if($s.TimeStamperCertificate){$s.TimeStamperCertificate.Subject}else{$null};"
            "TimestampIssuer=if($s.TimeStamperCertificate){$s.TimeStamperCertificate.Issuer}else{$null};"
            "TimestampNotBefore=if($s.TimeStamperCertificate){$s.TimeStamperCertificate.NotBefore.ToUniversalTime().ToString('o')}else{$null};"
            "TimestampNotAfter=if($s.TimeStamperCertificate){$s.TimeStamperCertificate.NotAfter.ToUniversalTime().ToString('o')}else{$null}"
            "}|ConvertTo-Json -Compress"
        ),
    ]
    try:
        completed = execute(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            env=child_env,
        )
        value = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise ValueError("Authenticode inspection failed closed") from exc
    if not isinstance(value, dict) or not isinstance(value.get("Status"), str):
        raise ValueError("Authenticode inspection returned invalid data")
    def optional_string(name: str) -> str | None:
        item = value.get(name)
        if item is not None and not isinstance(item, str):
            raise ValueError(f"Authenticode inspection returned invalid {name} data")
        return item

    status = value["Status"]
    subject = optional_string("Subject")
    issuer = optional_string("Issuer")
    certificate_valid_from = optional_string("NotBefore")
    certificate_valid_to = optional_string("NotAfter")
    thumbprint = optional_string("Thumbprint")
    timestamp_present = value.get("TimestampPresent", False)
    if not isinstance(timestamp_present, bool):
        raise ValueError("Authenticode inspection returned invalid timestamp evidence")
    timestamp_subject = optional_string("TimestampSubject")
    timestamp_issuer = optional_string("TimestampIssuer")
    timestamp_valid_from = optional_string("TimestampNotBefore")
    timestamp_valid_to = optional_string("TimestampNotAfter")

    if status == "Valid" and any(
        item is None
        for item in (
            subject,
            issuer,
            certificate_valid_from,
            certificate_valid_to,
            thumbprint,
        )
    ):
        raise ValueError("Authenticode inspection returned incomplete signer evidence")

    timestamp_items = (
        timestamp_subject,
        timestamp_issuer,
        timestamp_valid_from,
        timestamp_valid_to,
    )
    if timestamp_present:
        if any(item is None for item in timestamp_items):
            raise ValueError("Authenticode inspection returned incomplete timestamp evidence")
        timestamp_status: Literal["absent", "present"] = "present"
    else:
        if any(item is not None for item in timestamp_items):
            raise ValueError("Authenticode inspection returned inconsistent timestamp evidence")
        timestamp_status = "absent"

    return AuthenticodeSignature(
        status=status,
        subject=subject,
        thumbprint=thumbprint,
        issuer=issuer,
        certificate_valid_from=certificate_valid_from,
        certificate_valid_to=certificate_valid_to,
        timestamp_status=timestamp_status,
        timestamp_subject=timestamp_subject,
        timestamp_issuer=timestamp_issuer,
        timestamp_valid_from=timestamp_valid_from,
        timestamp_valid_to=timestamp_valid_to,
    )


def verify_windows_authenticode(
    path: str | Path,
    policy: AuthenticodePolicy,
    *,
    inspector: Callable[[Path], AuthenticodeSignature] | None = None,
) -> AuthenticodeSignature:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Authenticode target must be an existing regular file")
    inspect_signature = inspector or inspect_windows_authenticode
    signature = inspect_signature(source)
    if policy.required and signature.status != "Valid":
        raise ValueError("required Authenticode signature is not valid")
    if (
        policy.expected_subject is not None
        and signature.subject != policy.expected_subject
    ):
        raise ValueError("Authenticode publisher subject does not match policy")
    if policy.expected_thumbprints:
        thumbprint = (signature.thumbprint or "").replace(" ", "").upper()
        if thumbprint not in policy.expected_thumbprints:
            raise ValueError("Authenticode certificate thumbprint does not match policy")
    return signature
