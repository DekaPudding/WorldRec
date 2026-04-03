from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.instance_access_type import normalize_access_type_query, normalize_access_type_value
from app.core.tag_utils import split_tags
from app.models.dto import RecommendationItem
from app.models.entities import VisitHistory


@dataclass(slots=True)
class RecommendationResponse:
    items: list[RecommendationItem]
    source: str


@dataclass(slots=True)
class OpenAIRecommendationResult:
    items: list[RecommendationItem]
    status: str


_RECOMMENDATION_RESPONSE_SCHEMA = {
    "name": "worldrec_recommendations",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "index": {
                            "type": "integer",
                            "description": "候補一覧の1始まりの番号。",
                        },
                        "reason": {
                            "type": "string",
                            "description": "その候補を選んだ簡潔な理由。",
                        },
                    },
                    "required": ["index", "reason"],
                },
                "maxItems": 5,
            }
        },
        "required": ["recommendations"],
    },
}


def format_recommendation_message(response: RecommendationResponse) -> str:
    if response.source == "empty_query":
        return "検索語を入力してください。"
    if response.source == "no_history":
        return "検索対象の履歴がありません。履歴が記録されてから再度お試しください。"
    if response.source == "openai":
        return "AI検索で候補を抽出しました。"
    if response.source == "openai_api_key_missing":
        if response.items:
            return (
                "OpenAI API キーが未設定のため、"
                "訪問履歴ベースで候補を表示します。"
            )
        return "OpenAI API キーが未設定で、候補も見つかりませんでした。"
    if response.source == "openai_error":
        if response.items:
            return (
                "OpenAI への問い合わせに失敗したため、"
                "訪問履歴ベースで候補を表示します。"
            )
        return "OpenAI への問い合わせに失敗し、候補も見つかりませんでした。"
    if response.source == "openai_refusal":
        return "AI が候補生成を完了できなかったため、訪問履歴ベースで候補を表示します。"
    if response.source == "openai_schema_mismatch":
        return "AI 応答の形式が不正だったため、訪問履歴ベースで候補を表示します。"
    if response.source == "openai_no_recommendations":
        return "AI は候補を返しませんでした。訪問履歴ベースで候補を表示します。"
    if response.items:
        return "訪問履歴から条件に近い候補を表示します。"
    return "条件に合う候補が見つかりませんでした。"


class RecommendationService:
    def __init__(
        self,
        openai_endpoint: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        openai_api_key: str | None = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
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
            openai_result = self._openai_recommend(query, histories, top_n)
            if openai_result.status == "success":
                return RecommendationResponse(items=openai_result.items, source="openai")
            if openai_result.status == "refusal":
                self.logger.warning("OpenAI recommendation refused the request")
                return RecommendationResponse(items=fallback_items, source="openai_refusal")
            if openai_result.status == "schema_mismatch":
                self.logger.warning("OpenAI recommendation returned a schema-mismatched response")
                return RecommendationResponse(items=fallback_items, source="openai_schema_mismatch")
            if openai_result.status == "no_recommendations":
                self.logger.info("OpenAI recommendation returned no candidates")
                return RecommendationResponse(items=fallback_items, source="openai_no_recommendations")
        except Exception:
            self.logger.exception("OpenAI recommendation request failed")
            return RecommendationResponse(items=fallback_items, source="openai_error")

        return RecommendationResponse(items=fallback_items, source="fallback")

    def _openai_recommend(
        self,
        query: str,
        histories: list[VisitHistory],
        top_n: int,
    ) -> OpenAIRecommendationResult:
        candidate_lines = [
            (
                f"{i + 1}. {h.world_name} | visited_at={h.visited_at}"
                f" | instance_type={h.instance_access_type or '-'}"
                f" | tags={h.tags or '-'}"
                f" | memo={self._compact_text(h.memo)}"
            )
            for i, h in enumerate(histories[:50])
        ]
        system_prompt = self._build_system_prompt(max_items=min(top_n, 5))
        user_prompt = f"ユーザー要望: {query}\n\n候補一覧:\n" + "\n".join(candidate_lines)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {
                "type": "json_schema",
                "json_schema": _RECOMMENDATION_RESPONSE_SCHEMA,
            },
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
        parsed, status = self._extract_structured_openai_data(response_json)
        if status != "success":
            return OpenAIRecommendationResult(items=[], status=status)
        recommendations = parsed.get("recommendations")
        if not isinstance(recommendations, list):
            return OpenAIRecommendationResult(items=[], status="schema_mismatch")
        result: list[RecommendationItem] = []
        for item in recommendations:
            if not isinstance(item, dict):
                continue
            idx = int(item.get("index", 0)) - 1
            if idx < 0 or idx >= len(histories):
                continue
            history = histories[idx]
            reason = str(item.get("reason") or "条件一致").strip() or "条件一致"
            result.append(
                RecommendationItem(
                    world_name=history.world_name,
                    visited_at=history.visited_at,
                    reason=reason,
                )
            )
            if len(result) >= top_n:
                break

        if result:
            return OpenAIRecommendationResult(items=result, status="success")
        return OpenAIRecommendationResult(items=[], status="no_recommendations")

    @staticmethod
    def _extract_structured_openai_data(response_json: dict) -> tuple[dict, str]:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            return ({}, "schema_mismatch")
        first = choices[0]
        if not isinstance(first, dict):
            return ({}, "schema_mismatch")
        message = first.get("message")
        if not isinstance(message, dict):
            return ({}, "schema_mismatch")
        refusal = message.get("refusal")
        if refusal:
            return ({}, "refusal")
        content = message.get("content")
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    return (parsed, "success")
                return ({}, "schema_mismatch")
            except json.JSONDecodeError:
                return ({}, "schema_mismatch")
        return ({}, "schema_mismatch")

    @staticmethod
    def _build_system_prompt(max_items: int) -> str:
        return (
            "あなたはVRChatワールド履歴推薦アシスタントです。"
            "ユーザー要望に最も合う候補だけを選んでください。"
            f"候補は最大{max_items}件までに制限してください。"
            "候補一覧に含まれないワールドを作らないでください。"
            "index は候補一覧の1始まりの番号をそのまま返してください。"
            "reason は日本語で簡潔に、候補一覧の情報とユーザー要望に基づいて説明してください。"
            "スキーマにないキーは出力しないでください。"
            "応答は必ず指定された JSON スキーマに従ってください。"
        )

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
        access_type = normalize_access_type_value(history.instance_access_type) or ""

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
