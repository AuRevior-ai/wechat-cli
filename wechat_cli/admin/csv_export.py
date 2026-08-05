"""Non-overwriting export of plaintext license keys for the sole administrator."""

from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

_FIELDS = (
    "license_id",
    "license_key",
    "license_hint",
    "maximum_devices",
    "release_channel",
    "created_at",
)


def _validated_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise ValueError(f"license row {index} must be an object")
        selected: dict[str, Any] = {}
        for field in _FIELDS:
            value = row.get(field)
            if field in {"license_id", "license_key"} and (
                not isinstance(value, str) or not value
            ):
                raise ValueError(f"license row {index} is missing {field}")
            if value is None:
                value = ""
            selected[field] = value
        result.append(selected)
    if not result:
        raise ValueError("at least one license row is required")
    return result


def export_license_csv(
    path: str | Path,
    rows: Iterable[Mapping[str, Any]],
) -> Path:
    """Create a UTF-8 BOM CSV exactly once and never overwrite it."""

    destination = Path(path)
    validated = _validated_rows(rows)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        created = True
        with os.fdopen(descriptor, "wb", closefd=True) as binary:
            descriptor = None
            with io.TextIOWrapper(
                binary,
                encoding="utf-8-sig",
                newline="",
                write_through=True,
            ) as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=list(_FIELDS),
                    extrasaction="ignore",
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(validated)
                stream.flush()
                os.fsync(binary.fileno())
        return destination
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            try:
                destination.unlink()
            except FileNotFoundError:
                pass
        raise
