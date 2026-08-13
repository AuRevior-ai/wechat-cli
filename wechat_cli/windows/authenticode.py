"""Windows Authenticode verification boundary."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class AuthenticodeSignature:
    status: str
    subject: str | None
    thumbprint: str | None


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


def inspect_windows_authenticode(
    path: str | Path,
    *,
    runner=None,
) -> AuthenticodeSignature:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Authenticode target must be an existing regular file")
    execute = runner or subprocess.run
    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "$s=Get-AuthenticodeSignature -LiteralPath $args[0];"
            "[pscustomobject]@{"
            "Status=$s.Status.ToString();"
            "Subject=if($s.SignerCertificate){$s.SignerCertificate.Subject}else{$null};"
            "Thumbprint=if($s.SignerCertificate){$s.SignerCertificate.Thumbprint}else{$null}"
            "}|ConvertTo-Json -Compress"
        ),
        str(source),
    ]
    try:
        completed = execute(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        value = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise ValueError("Authenticode inspection failed closed") from exc
    if not isinstance(value, dict) or not isinstance(value.get("Status"), str):
        raise ValueError("Authenticode inspection returned invalid data")
    subject = value.get("Subject")
    thumbprint = value.get("Thumbprint")
    if subject is not None and not isinstance(subject, str):
        raise ValueError("Authenticode inspection returned invalid publisher data")
    if thumbprint is not None and not isinstance(thumbprint, str):
        raise ValueError("Authenticode inspection returned invalid thumbprint data")
    return AuthenticodeSignature(value["Status"], subject, thumbprint)


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
