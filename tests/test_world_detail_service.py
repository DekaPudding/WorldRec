from __future__ import annotations

import unittest

from app.core.world_detail_service import WorldDetailService


class WorldDetailServiceTest(unittest.TestCase):
    def test_extract_platforms_from_unity_packages(self) -> None:
        service = WorldDetailService()
        data = {
            "unityPackages": [
                {"platform": "standalonewindows"},
                {"platform": "android"},
            ]
        }
        platforms = service._extract_platforms(data)  # noqa: SLF001
        self.assertEqual(platforms, ["Android/Quest", "PC"])

    def test_extract_platforms_from_alternative_fields(self) -> None:
        service = WorldDetailService()
        data = {
            "platforms": ["windows", "quest"],
            "tags": ["platform:standalonewindows", "platform:android"],
        }
        platforms = service._extract_platforms(data)  # noqa: SLF001
        self.assertEqual(platforms, ["Android/Quest", "PC"])


if __name__ == "__main__":
    unittest.main()
