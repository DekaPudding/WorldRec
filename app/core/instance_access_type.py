from __future__ import annotations


_DISPLAY_MAPPING: dict[str, str] = {
    "friends+": "Friends+",
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
    "hidden": "friends+",
    "非公開": "friends+",
    "group": "group",
    "グループ": "group",
    "private": "private",
    "offline": "offline",
}


def to_display_access_type(value: str | None) -> str:
    normalized = normalize_access_type_value(value)
    if not normalized:
        return "不明"
    return _DISPLAY_MAPPING.get(normalized, normalized)


def normalize_access_type_value(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    # VRChat logs often emit hidden for invite-plus style instances.
    if normalized == "hidden":
        return "friends+"
    return normalized


def normalize_access_type_query(value: str | None) -> str | None:
    normalized = normalize_access_type_value(value)
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
        ("Group", "group"),
        ("Private", "private"),
        ("Offline", "offline"),
    ]
