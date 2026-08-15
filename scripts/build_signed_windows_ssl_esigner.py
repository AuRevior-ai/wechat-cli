"""Controlled SSL.com eSigner entrypoint for signed Windows staging artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build and Authenticode-sign the Windows app, Launcher, and installer "
            "with a preconfigured SSL.com eSigner CKA certificate."
        )
    )
    parser.add_argument("--signtool-path", required=True)
    parser.add_argument("--certificate-thumbprint", required=True)
    parser.add_argument("--launcher-config", required=True)
    parser.add_argument("--trust-profile", required=True)
    return parser


def main(argv=None, *, provider_factory=None, installer_creator=None) -> int:
    args = build_parser().parse_args(argv)

    if provider_factory is None:
        from scripts.ssl_esigner_signing import SslEsignerSigningProvider

        provider_factory = SslEsignerSigningProvider
    if installer_creator is None:
        from scripts.package_windows_app import create_production_installer

        installer_creator = create_production_installer

    provider = provider_factory(
        signtool_path=Path(args.signtool_path),
        certificate_thumbprint=args.certificate_thumbprint,
    )
    installer, legacy_zip, update_zip = installer_creator(
        launcher_config_path=args.launcher_config,
        trust_profile_path=args.trust_profile,
        signing_provider=provider,
    )

    print(f"Signed installer: {installer}")
    print(f"Signed bootstrap archive: {legacy_zip}")
    print(f"Signed update archive: {update_zip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
