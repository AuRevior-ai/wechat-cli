from __future__ import annotations

from pathlib import Path


class PackagingPathError(ValueError):
    pass


def assert_outside_repository(path: Path, *, repository_root: Path) -> Path:
    resolved = Path(path).resolve(strict=False)
    root = Path(repository_root).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        return resolved
    raise PackagingPathError("packaging output must be outside the repository")
