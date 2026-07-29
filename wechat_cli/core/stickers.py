"""Resolve WeChat sticker metadata from the local encrypted-database cache."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from typing import Any


def load_sticker_metadata(cache) -> dict[str, dict[str, str]]:
    try:
        path = cache.get(os.path.join("emoticon", "emoticon.db"))
    except (AttributeError, OSError):
        return {}
    if not path:
        return {}
    result: dict[str, dict[str, str]] = {}
    try:
        with closing(sqlite3.connect(path)) as connection:
            rows = connection.execute(
                "SELECT md5, aes_key, cdn_url, encrypt_url, thumb_url "
                "FROM kNonStoreEmoticonTable"
            )
            for md5, aes_key, cdn_url, encrypt_url, thumb_url in rows:
                normalized = str(md5 or "").strip().lower()
                if len(normalized) != 32:
                    continue
                result[normalized] = {
                    key: value
                    for key, value in {
                        "md5": normalized,
                        "aes_key": str(aes_key or "").strip(),
                        "url": str(
                            cdn_url or encrypt_url or thumb_url or ""
                        ).strip(),
                    }.items()
                    if value
                }
    except (sqlite3.Error, OSError):
        return {}
    return result


def enrich_sticker_media(
    items: list[dict[str, Any]],
    metadata: dict[str, dict[str, str]],
) -> None:
    def enrich_one(item: dict[str, Any]) -> None:
        media = item.get("media")
        if isinstance(media, dict):
            md5 = str(media.get("md5") or "").lower()
            known = metadata.get(md5)
            if known:
                for key in ("aes_key", "url"):
                    if not media.get(key) and known.get(key):
                        media[key] = known[key]
        for child in item.get("children") or []:
            enrich_one(child)

    for item in items:
        enrich_one(item)
        forwarded = item.get("forwarded") or {}
        for child in forwarded.get("items") or []:
            enrich_one(child)
