from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class WorldVisitEvent:
    visited_at: datetime
    world_name: str
    world_id: str | None
    instance_id: str | None
    instance_access_type: str | None
    instance_nonce: str | None
    instance_raw_tags: str | None


@dataclass(slots=True)
class _PendingInstanceContext:
    captured_at: datetime
    world_id: str | None
    instance_id: str | None
    instance_access_type: str | None
    instance_nonce: str | None
    instance_raw_tags: str | None


class WorldEventParser:
    _timestamp_re = re.compile(r"^(?P<ts>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})")
    _room_patterns = (
        re.compile(r"Joining or Creating Room:\s*(?P<room>.+)$"),
        re.compile(r"Entering Room:\s*(?P<room>.+)$"),
        re.compile(r"Joining Room:\s*(?P<room>.+)$"),
        re.compile(r"OnJoinedRoom[:\s]+(?P<room>.+)$"),
    )
    _world_id_re = re.compile(r"(wrld_[A-Za-z0-9\-]+)")
    _instance_id_patterns = (
        re.compile(r"wrld_[A-Za-z0-9\-]+:(?P<iid>[A-Za-z0-9~\-\(\)_\+,\.]+)"),
        re.compile(r"instance[_\s]?id[=: ](?P<iid>[A-Za-z0-9~\-\(\)_\+,\.]+)", re.I),
    )
    _instance_access_types = (
        "friends+",
        "invite+",
        "public",
        "friends",
        "invite",
        "group",
        "hidden",
        "private",
        "offline",
    )
    _nonce_re = re.compile(r"~nonce\((?P<nonce>[^)]*)\)", re.I)
    _instance_tag_re = re.compile(r"~[A-Za-z0-9+\-]+(?:\([^)]*\))?")
    _home_line_re = re.compile(
        r"(going\s+home|return(?:ing)?\s+to\s+home|entering\s+home|home\s+world)",
        re.I,
    )
    _home_world_names = {"home", "ホーム", "ホームワールド"}
    _context_ttl_seconds = 45

    def __init__(self) -> None:
        self._pending_context: _PendingInstanceContext | None = None

    def parse_line(self, line: str) -> WorldVisitEvent | None:
        if self._home_line_re.search(line):
            return None

        timestamp = self._extract_timestamp(line)
        self._update_pending_context(line, timestamp)

        room_text: str | None = None
        for pattern in self._room_patterns:
            match = pattern.search(line)
            if match:
                room_text = match.group("room").strip()
                break

        if not room_text:
            return None

        visited_at = timestamp or datetime.now()

        world_id = self._extract_world_id(room_text, line)

        instance_id = self._extract_instance_id(line, room_text)
        instance_access_type, instance_nonce, instance_raw_tags = self._extract_instance_metadata(
            instance_id,
            room_text,
            line,
        )
        (
            world_id,
            instance_id,
            instance_access_type,
            instance_nonce,
            instance_raw_tags,
        ) = self._fill_from_pending_context(
            visited_at=visited_at,
            world_id=world_id,
            instance_id=instance_id,
            instance_access_type=instance_access_type,
            instance_nonce=instance_nonce,
            instance_raw_tags=instance_raw_tags,
        )

        world_name = self._extract_world_name(room_text, world_id)
        if not self._looks_like_world_name(world_name):
            return None
        if world_name.strip().lower() in self._home_world_names:
            return None
        return WorldVisitEvent(
            visited_at=visited_at,
            world_name=world_name,
            world_id=world_id,
            instance_id=instance_id,
            instance_access_type=instance_access_type,
            instance_nonce=instance_nonce,
            instance_raw_tags=instance_raw_tags,
        )

    def _update_pending_context(self, line: str, timestamp: datetime | None) -> None:
        world_id = self._extract_world_id(line, line)
        instance_id = self._extract_instance_id(line, line)
        instance_access_type, instance_nonce, instance_raw_tags = self._extract_instance_metadata(
            instance_id,
            line,
            line,
        )
        if not any([world_id, instance_id, instance_access_type, instance_raw_tags]):
            return
        self._pending_context = _PendingInstanceContext(
            captured_at=timestamp or datetime.now(),
            world_id=world_id,
            instance_id=instance_id,
            instance_access_type=instance_access_type,
            instance_nonce=instance_nonce,
            instance_raw_tags=instance_raw_tags,
        )

    def _fill_from_pending_context(
        self,
        visited_at: datetime,
        world_id: str | None,
        instance_id: str | None,
        instance_access_type: str | None,
        instance_nonce: str | None,
        instance_raw_tags: str | None,
    ) -> tuple[str | None, str | None, str | None, str | None, str | None]:
        context = self._pending_context
        if context is None:
            return (
                world_id,
                instance_id,
                instance_access_type,
                instance_nonce,
                instance_raw_tags,
            )
        if abs((visited_at - context.captured_at).total_seconds()) > self._context_ttl_seconds:
            return (
                world_id,
                instance_id,
                instance_access_type,
                instance_nonce,
                instance_raw_tags,
            )
        if world_id and context.world_id and world_id != context.world_id:
            return (
                world_id,
                instance_id,
                instance_access_type,
                instance_nonce,
                instance_raw_tags,
            )
        return (
            world_id or context.world_id,
            instance_id or context.instance_id,
            instance_access_type or context.instance_access_type,
            instance_nonce or context.instance_nonce,
            instance_raw_tags or context.instance_raw_tags,
        )

    def _extract_timestamp(self, line: str) -> datetime | None:
        timestamp_match = self._timestamp_re.search(line)
        if not timestamp_match:
            return None
        try:
            return datetime.strptime(timestamp_match.group("ts"), "%Y.%m.%d %H:%M:%S")
        except ValueError:
            return None

    @staticmethod
    def _extract_world_name(room_text: str, world_id: str | None) -> str:
        normalized = room_text.replace("|", " ").strip()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"^\[[^\]]+\]\s*", "", normalized)
        normalized = normalized.split("  ", 1)[0].strip()

        if "(" in normalized and ")" in normalized:
            name = normalized.split("(", 1)[0].strip(" -:")
            if name:
                return name

        if " - " in normalized:
            left = normalized.split(" - ", 1)[0].strip()
            if left and not left.startswith("wrld_"):
                return left

        if world_id and world_id in normalized:
            cleaned = normalized.replace(world_id, "").strip(" -:|")
            if cleaned:
                return cleaned
            return world_id

        return normalized.strip()

    @staticmethod
    def _looks_like_world_name(name: str) -> bool:
        if not name:
            return False
        if len(name) < 2 or len(name) > 120:
            return False
        lowered = name.lower()
        blocked_tokens = (
            "api",
            "http://",
            "https://",
            "exception",
            "error",
            "warning",
            "debug",
            "roommanager",
        )
        if any(token in lowered for token in blocked_tokens):
            return False
        if name.startswith("wrld_"):
            return False
        return True

    def _extract_instance_id(self, line: str, room_text: str) -> str | None:
        for pattern in self._instance_id_patterns:
            for target in (room_text, line):
                match = pattern.search(target)
                if match:
                    return match.group("iid")
        return None

    def _extract_world_id(self, room_text: str, line: str) -> str | None:
        for target in (room_text, line):
            match = self._world_id_re.search(target)
            if match:
                return match.group(1)
        return None

    def _extract_instance_metadata(
        self,
        instance_id: str | None,
        room_text: str,
        line: str,
    ) -> tuple[str | None, str | None, str | None]:
        raw_tags = self._extract_raw_tags(instance_id, room_text, line)
        if not raw_tags:
            return (None, None, None)
        nonce_match = self._nonce_re.search(raw_tags)
        instance_nonce = nonce_match.group("nonce") if nonce_match else None

        access_type = None
        tags = [segment.strip().lower() for segment in raw_tags.split("~") if segment.strip()]
        for tag in tags:
            normalized = tag.split("(", 1)[0]
            if normalized in self._instance_access_types:
                access_type = normalized
                break

        return (access_type, instance_nonce, raw_tags)

    def _extract_raw_tags(self, instance_id: str | None, room_text: str, line: str) -> str | None:
        if instance_id and "~" in instance_id:
            return "~" + instance_id.split("~", 1)[1]

        tags: list[str] = []
        for target in (room_text, line):
            tags.extend(self._instance_tag_re.findall(target))
        if not tags:
            return None
        return "".join(tags)
