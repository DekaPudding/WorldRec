from __future__ import annotations

import unittest

from app.core.world_event_parser import WorldEventParser


class WorldEventParserTest(unittest.TestCase):
    def test_fill_instance_context_from_destination_line(self) -> None:
        parser = WorldEventParser()

        destination_line = (
            "2026.02.23 13:58:18 Debug - [Behaviour] Destination set: "
            "wrld_36e600ac-3b08-4736-b0c0-5d0fd4edb0d7:02641~hidden(usr_xxx)~region(jp)"
        )
        entering_line = (
            "2026.02.23 13:58:20 Debug - [Behaviour] Entering Room: Bar 夜更けの語らい"
        )

        self.assertIsNone(parser.parse_line(destination_line))
        event = parser.parse_line(entering_line)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.world_id, "wrld_36e600ac-3b08-4736-b0c0-5d0fd4edb0d7")
        self.assertEqual(event.instance_access_type, "hidden")
        self.assertIn("~hidden", event.instance_raw_tags or "")

    def test_region_only_does_not_force_access_type(self) -> None:
        parser = WorldEventParser()

        destination_line = (
            "2026.02.22 23:55:42 Debug - [Behaviour] Destination set: "
            "wrld_f5f8b3dc-6f33-4b34-97f3-83add2fb224d:22522~region(jp)"
        )
        entering_line = (
            "2026.02.22 23:55:50 Debug - [Behaviour] Joining or Creating Room: "
            "日本語話者向け集会場「FUJIYAMA」JP"
        )

        self.assertIsNone(parser.parse_line(destination_line))
        event = parser.parse_line(entering_line)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.world_id, "wrld_f5f8b3dc-6f33-4b34-97f3-83add2fb224d")
        self.assertIsNone(event.instance_access_type)


if __name__ == "__main__":
    unittest.main()
