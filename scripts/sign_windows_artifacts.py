"""Explicit Windows artifact signing-provider orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from wechat_cli.windows.authenticode import (
    AuthenticodePolicy,
    verify_windows_authenticode,
)


class WindowsSigningProvider(Protocol):
    """A caller-supplied signer; credentials are never discovered here."""

    def sign(self, path: Path) -> None: ...


def sign_and_verify_windows_artifacts(
    paths: Sequence[str | Path],
    *,
    provider: WindowsSigningProvider,
    policy: AuthenticodePolicy,
    verifier=None,
) -> tuple[Path, ...]:
    verify = verifier or verify_windows_authenticode
    verified: list[Path] = []
    for value in paths:
        path = Path(value)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Windows signing target must be an existing regular file")
        provider.sign(path)
        verify(path, policy)
        verified.append(path)
    return tuple(verified)
