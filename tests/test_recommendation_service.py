from __future__ import annotations

import unittest

from app.core.recommendation_service import RecommendationService
from app.models.entities import VisitHistory


class RecommendationServiceTest(unittest.TestCase):
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
        self.assertIn("インスタンスタイプ一致", items[0].reason)

    def test_fallback_handles_query_without_strong_matches(self) -> None:
        service = RecommendationService()
        histories = [
            VisitHistory(id=1, visited_at="2026-02-23T10:00:00", world_name="World A"),
            VisitHistory(id=2, visited_at="2026-02-22T10:00:00", world_name="World B"),
        ]

        items = service._fallback_recommend("未知の検索語", histories, top_n=2)
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item.reason for item in items))


if __name__ == "__main__":
    unittest.main()
