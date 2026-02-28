from __future__ import annotations


_DISPLAY_MAPPING: dict[str, str] = {
    "hidden": "Invite系(非公開)",
}

_QUERY_MAPPING: dict[str, str] = {
    "public": "public",
    "パブリック": "public",
    "friends": "friends",
    "friend": "friends",
    "フレンド": "friends",
    "friends+": "friends+",
    "friend+": "friends+",
    "invite": "invite",
    "invite+": "invite+",
    "インバイト": "invite",
    "hidden": "hidden",
    "非公開": "hidden",
    "group": "group",
    "グループ": "group",
    "private": "private",
    "offline": "offline",
}


def to_display_access_type(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return "不明"
    return _DISPLAY_MAPPING.get(normalized, value.strip())


def normalize_access_type_query(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    return _QUERY_MAPPING.get(normalized)


def get_access_type_options() -> list[tuple[str, str | None]]:
    return [
        ("すべて", None),
        ("Public", "public"),
        ("Friends", "friends"),
        ("Friends+", "friends+"),
        ("Invite", "invite"),
        ("Invite+", "invite+"),
        ("Invite系(非公開)", "hidden"),
        ("Group", "group"),
        ("Private", "private"),
        ("Offline", "offline"),
    ]
