from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.instance_access_type import normalize_access_type_query
from app.core.tag_utils import split_tags
from app.models.dto import RecommendationItem
from app.models.entities import VisitHistory


@dataclass(slots=True)
class RecommendationResponse:
    items: list[RecommendationItem]
    source: str


class RecommendationService:
    def __init__(
        self,
        openai_endpoint: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        openai_api_key: str | None = None,
    ) -> None:
        self.openai_endpoint = openai_endpoint.rstrip("/")
        self.model = model
        self.openai_api_key = (
            openai_api_key
            or os.environ.get("WORLDREC_OPENAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()

    def recommend(self, query: str, histories: list[VisitHistory], top_n: int = 5) -> RecommendationResponse:
        if not query.strip():
            return RecommendationResponse(items=[], source="empty_query")

        if not histories:
            return RecommendationResponse(items=[], source="no_history")

        fallback_items = self._fallback_recommend(query, histories, top_n)
        if not self.openai_api_key:
            return RecommendationResponse(items=fallback_items, source="openai_api_key_missing")

        try:
            openai_items = self._openai_recommend(query, histories, top_n)
            if openai_items:
                return RecommendationResponse(items=openai_items, source="openai")
        except Exception:
            return RecommendationResponse(items=fallback_items, source="openai_error")

        return RecommendationResponse(items=fallback_items, source="fallback")

    def _openai_recommend(self, query: str, histories: list[VisitHistory], top_n: int) -> list[RecommendationItem]:
        candidate_lines = [
            (
                f"{i + 1}. {h.world_name} | visited_at={h.visited_at}"
                f" | instance_type={h.instance_access_type or '-'}"
                f" | tags={h.tags or '-'}"
                f" | memo={self._compact_text(h.memo)}"
            )
            for i, h in enumerate(histories[:50])
        ]
        system_prompt = (
            "あなたはVRChatワールド履歴推薦アシスタントです。"
            "ユーザー要望に合うワールドを最大5件、理由つきで選んでください。"
            "出力はJSON配列のみ。各要素は {\"index\":番号, \"reason\":\"理由\"}。"
            "JSON以外は一切出力しないでください。"
        )
        user_prompt = f"ユーザー要望: {query}\n\n候補一覧:\n" + "\n".join(candidate_lines)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        request = urllib.request.Request(
            f"{self.openai_endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")

        response_json = json.loads(body)
        text = self._extract_openai_text(response_json).strip()
        match = re.search(r"\[.*\]", text, flags=re.S)
        if not match:
            return []

        parsed = json.loads(match.group(0))
        result: list[RecommendationItem] = []
        for item in parsed:
            idx = int(item.get("index", 0)) - 1
            if idx < 0 or idx >= len(histories):
                continue
            history = histories[idx]
            reason = str(item.get("reason", "条件一致"))
            result.append(
                RecommendationItem(
                    world_name=history.world_name,
                    visited_at=history.visited_at,
                    reason=reason,
                )
            )
            if len(result) >= top_n:
                break

        return result

    @staticmethod
    def _extract_openai_text(response_json: dict) -> str:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        message = first.get("message")
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        if isinstance(content, str):
            return content
        return ""

    def _fallback_recommend(self, query: str, histories: list[VisitHistory], top_n: int) -> list[RecommendationItem]:
        tokens = [t for t in re.split(r"\s+", query.lower()) if t]
        query_access_types = self._extract_query_access_types(query)
        scored: list[tuple[int, str, VisitHistory]] = []

        for index, history in enumerate(histories):
            score, reason = self._score_history(history, tokens, query_access_types, index)
            scored.append((score, reason, history))

        scored.sort(key=lambda x: (x[0], x[2].visited_at), reverse=True)

        items: list[RecommendationItem] = []
        for score, reason, history in scored[:top_n]:
            items.append(
                RecommendationItem(
                    world_name=history.world_name,
                    visited_at=history.visited_at,
                    reason=reason if score > 0 else "履歴内の最近訪問ワールド",
                )
            )

        return items

    @staticmethod
    def _compact_text(value: str | None, max_length: int = 80) -> str:
        if not value:
            return "-"
        compact = " ".join(value.split())
        if len(compact) <= max_length:
            return compact
        return compact[: max_length - 3] + "..."

    def _score_history(
        self,
        history: VisitHistory,
        tokens: list[str],
        query_access_types: set[str],
        index: int,
    ) -> tuple[int, str]:
        score = 0
        reasons: list[str] = []

        world_name = history.world_name.lower()
        memo = (history.memo or "").lower()
        tags = [tag.lower() for tag in split_tags(history.tags)]
        access_type = (history.instance_access_type or "").lower()

        if query_access_types and access_type and access_type in query_access_types:
            score += 9
            reasons.append(f"インスタンスタイプ一致({access_type})")

        for token in tokens:
            if token in world_name:
                score += 4
                reasons.append(f"ワールド名:{token}")
            if token in memo:
                score += 2
                reasons.append(f"メモ:{token}")
            for tag in tags:
                if token == tag:
                    score += 6
                    reasons.append(f"タグ完全一致:{tag}")
                    break
                if token in tag:
                    score += 4
                    reasons.append(f"タグ一致:{tag}")
                    break

        # 新しい履歴ほど少し優先する
        score += max(0, 3 - index // 5)

        if not reasons:
            return (score, "履歴内の最近訪問ワールド")
        unique_reasons = list(dict.fromkeys(reasons))
        return (score, " / ".join(unique_reasons[:3]))

    def _extract_query_access_types(self, query: str) -> set[str]:
        lowered = query.lower()
        tokens = re.split(r"[\\s,、]+", lowered)
        found: set[str] = set()
        for token in tokens:
            normalized = normalize_access_type_query(token)
            if normalized:
                found.add(normalized)
        if "非公開" in query:
            found.add("friends+")
        return found
