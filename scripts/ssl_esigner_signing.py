"""SSL.com eSigner provider boundary for Windows Authenticode signing.

This adapter assumes SSL.com eSigner CKA has already been installed, configured,
and has loaded the approved code-signing certificate into the current user's
Windows certificate store. Account credentials, TOTP secrets, CKA master keys,
and certificate provisioning are deliberately outside this module.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


_SSL_TIMESTAMP_URL = "http://ts.ssl.com"
_SHA1_THUMBPRINT = re.compile(r"[0-9A-F]{40}")


class SslEsignerSigningProvider:
    """Sign explicit files through a preconfigured SSL.com eSigner CKA identity."""

    def __init__(self, signtool_path, certificate_thumbprint, runner=subprocess.run):
        tool = Path(signtool_path)
        if tool.is_symlink() or not tool.is_file():
            raise ValueError("SSL.com eSigner SignTool path must be an existing regular file")

        normalized_thumbprint = str(certificate_thumbprint).replace(" ", "").upper()
        if _SHA1_THUMBPRINT.fullmatch(normalized_thumbprint) is None:
            raise ValueError("SSL.com eSigner certificate thumbprint must be 40 hexadecimal characters")

        self._signtool_path = tool
        self._certificate_thumbprint = normalized_thumbprint
        self._runner = runner

    def sign(self, path: Path) -> None:
        target = Path(path)
        if target.is_symlink() or not target.is_file():
            raise ValueError("SSL.com eSigner signing target must be an existing regular file")

        command = [
            str(self._signtool_path),
            "sign",
            "/fd",
            "sha256",
            "/tr",
            _SSL_TIMESTAMP_URL,
            "/td",
            "sha256",
            "/sha1",
            self._certificate_thumbprint,
            str(target),
        ]
        try:
            self._runner(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            raise ValueError("SSL.com eSigner signing failed closed") from None
