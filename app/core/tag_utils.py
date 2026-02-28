from __future__ import annotations

import re


def split_tags(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[,、\s]+", value)
    return [item.strip() for item in parts if item.strip()]


def normalize_tag_string(value: str | None) -> str | None:
    tags = split_tags(value)
    if not tags:
        return None

    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(tag)
    return ", ".join(unique)
