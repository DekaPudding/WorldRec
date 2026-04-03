from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.core.recommendation_service import (
    OpenAIRecommendationResult,
    RecommendationResponse,
    RecommendationService,
    format_recommendation_message,
)
from app.models.dto import RecommendationItem
from app.models.entities import VisitHistory


class RecommendationServiceTest(unittest.TestCase):
    def test_recommend_returns_empty_query_source_for_blank_query(self) -> None:
        service = RecommendationService(openai_api_key="")

        response = service.recommend("   ", [], top_n=1)

        self.assertEqual(response.source, "empty_query")
        self.assertEqual(response.items, [])

    def test_recommend_returns_no_history_source_when_histories_empty(self) -> None:
        service = RecommendationService(openai_api_key="")

        response = service.recommend("雑談", [], top_n=1)

        self.assertEqual(response.source, "no_history")
        self.assertEqual(response.items, [])

    def test_recommend_falls_back_when_openai_api_key_missing(self) -> None:
        service = RecommendationService(openai_api_key="")
        histories = [
            VisitHistory(
                id=1,
                visited_at="2026-02-23T13:58:20",
                world_name="Bar 夜更けの語らい",
                instance_access_type="hidden",
                tags="雑談, 夜",
                memo="静かで落ち着く",
            )
        ]

        response = service.recommend("夜", histories, top_n=1)
        self.assertEqual(response.source, "openai_api_key_missing")
        self.assertEqual(len(response.items), 1)

    def test_fallback_prefers_matching_access_type_and_tags(self) -> None:
        service = RecommendationService()
        histories = [
            VisitHistory(
                id=1,
                visited_at="2026-02-23T13:58:20",
                world_name="Bar 夜更けの語らい",
                instance_access_type="hidden",
                tags="雑談, 夜",
                memo="静かで落ち着く",
            ),
            VisitHistory(
                id=2,
                visited_at="2026-02-22T20:46:36",
                world_name="Friends Lounge",
                instance_access_type="friends",
                tags="雑談",
                memo="フレンド向け",
            ),
        ]

        items = service._fallback_recommend("非公開 夜", histories, top_n=2)
        self.assertEqual(items[0].world_name, "Bar 夜更けの語らい")
        self.assertTrue(items[0].reason)

    def test_fallback_handles_query_without_strong_matches(self) -> None:
        service = RecommendationService()
        histories = [
            VisitHistory(id=1, visited_at="2026-02-23T10:00:00", world_name="World A"),
            VisitHistory(id=2, visited_at="2026-02-22T10:00:00", world_name="World B"),
        ]

        items = service._fallback_recommend("未知の検索語", histories, top_n=2)
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item.reason for item in items))

    def test_recommend_returns_openai_source_when_openai_result_available(self) -> None:
        service = RecommendationService(openai_api_key="dummy")
        histories = [
            VisitHistory(id=1, visited_at="2026-02-23T10:00:00", world_name="World A"),
        ]
        expected_result = OpenAIRecommendationResult(
            items=service._fallback_recommend("World", histories, top_n=1),  # noqa: SLF001
            status="success",
        )
        service._openai_recommend = lambda query, input_histories, top_n: expected_result  # type: ignore[method-assign]

        response = service.recommend("World", histories, top_n=1)

        self.assertEqual(response.source, "openai")
        self.assertEqual(response.items, expected_result.items)

    def test_openai_request_uses_structured_output_schema(self) -> None:
        service = RecommendationService(openai_api_key="dummy", model="gpt-4o-mini")
        histories = [
            VisitHistory(id=1, visited_at="2026-02-23T10:00:00", world_name="World A"),
        ]
        captured: dict[str, object] = {}

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                payload = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "recommendations": [
                                            {"index": 1, "reason": "条件に合います"}
                                        ]
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }
                return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        def fake_urlopen(request, timeout=0):  # noqa: ANN001
            captured["timeout"] = timeout
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return _FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            response = service.recommend("World", histories, top_n=1)

        self.assertEqual(response.source, "openai")
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        response_format = payload["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertEqual(
            response_format["json_schema"]["name"],
            "worldrec_recommendations",
        )
        self.assertTrue(response_format["json_schema"]["strict"])
        messages = payload["messages"]
        self.assertIn("JSON スキーマ", messages[0]["content"])
        self.assertEqual(captured["timeout"], 30)

    def test_openai_recommend_returns_empty_when_structured_payload_is_invalid(self) -> None:
        service = RecommendationService(openai_api_key="dummy")
        histories = [
            VisitHistory(id=1, visited_at="2026-02-23T10:00:00", world_name="World A"),
        ]

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                payload = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({"unexpected": []}, ensure_ascii=False)
                            }
                        }
                    ]
                }
                return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=_FakeResponse()):
            result = service._openai_recommend("World", histories, top_n=1)  # noqa: SLF001

        self.assertEqual(result.items, [])
        self.assertEqual(result.status, "schema_mismatch")

    def test_recommend_uses_fallback_when_structured_payload_is_invalid(self) -> None:
        service = RecommendationService(openai_api_key="dummy")
        histories = [
            VisitHistory(id=1, visited_at="2026-02-23T10:00:00", world_name="World A"),
        ]

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                payload = {"choices": [{"message": {"content": "{\"broken\": true}"}}]}
                return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=_FakeResponse()):
            response = service.recommend("World", histories, top_n=1)

        self.assertEqual(response.source, "openai_schema_mismatch")
        self.assertEqual(len(response.items), 1)

    def test_recommend_uses_fallback_when_openai_refuses(self) -> None:
        service = RecommendationService(openai_api_key="dummy")
        histories = [
            VisitHistory(id=1, visited_at="2026-02-23T10:00:00", world_name="World A"),
        ]

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                payload = {"choices": [{"message": {"refusal": "safety"}}]}
                return json.dumps(payload, ensure_ascii=False).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=_FakeResponse()):
            response = service.recommend("World", histories, top_n=1)

        self.assertEqual(response.source, "openai_refusal")
        self.assertEqual(len(response.items), 1)

    def test_recommend_returns_fallback_when_openai_errors(self) -> None:
        service = RecommendationService(openai_api_key="dummy")
        histories = [
            VisitHistory(id=1, visited_at="2026-02-23T10:00:00", world_name="World A"),
        ]

        def raise_error(query: str, input_histories: list[VisitHistory], top_n: int):
            raise RuntimeError("boom")

        service._openai_recommend = raise_error  # type: ignore[method-assign]

        response = service.recommend("World", histories, top_n=1)

        self.assertEqual(response.source, "openai_error")
        self.assertEqual(len(response.items), 1)


class RecommendationMessageTest(unittest.TestCase):
    def test_format_response_message_for_openai_key_missing(self) -> None:
        response = RecommendationResponse(
            items=[],
            source="openai_api_key_missing",
        )

        message = format_recommendation_message(response)

        self.assertIn("OpenAI API キーが未設定", message)

    def test_format_response_message_for_openai_success(self) -> None:
        response = RecommendationResponse(
            items=[
                RecommendationItem(
                    world_name="World A",
                    visited_at="2026-02-23T10:00:00",
                    reason="一致",
                )
            ],
            source="openai",
        )

        message = format_recommendation_message(response)

        self.assertEqual(message, "AI検索で候補を抽出しました。")

    def test_format_response_message_for_fallback(self) -> None:
        response = RecommendationResponse(items=[], source="fallback")

        message = format_recommendation_message(response)

        self.assertEqual(message, "条件に合う候補が見つかりませんでした。")

    def test_format_response_message_for_schema_mismatch(self) -> None:
        response = RecommendationResponse(items=[], source="openai_schema_mismatch")

        message = format_recommendation_message(response)

        self.assertIn("形式が不正", message)


if __name__ == "__main__":
    unittest.main()
