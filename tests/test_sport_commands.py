import unittest
from datetime import datetime, timezone

from app.modules.cogs.sport_commands import (
    SportCommands,
    _discord_datetime,
    _leaderboard_text,
    _progress_bar,
)


class SportCommandHelpersTests(unittest.TestCase):
    def test_challenge_commands_require_name_and_have_autocomplete(self):
        commands_by_name = SportCommands.sport.children

        self.assertEqual(
            [option.name for option in commands_by_name["create"].body.options],
            ["channel", "name", "unit", "target", "duration_days"],
        )
        for command_name in ("join", "add", "status", "top", "finish"):
            option_names = [
                option.name
                for option in commands_by_name[command_name].body.options
            ]
            self.assertIn("challenge", option_names)
            self.assertIn(
                "challenge",
                commands_by_name[command_name].autocompleters,
            )

    def test_progress_bar_caps_completed_goal(self):
        self.assertEqual(_progress_bar(150, 100, width=4), "████")

    def test_progress_bar_shows_partial_progress(self):
        self.assertEqual(_progress_bar(50, 100, width=4), "██░░")

    def test_leaderboard_contains_places_mentions_and_values(self):
        text = _leaderboard_text(
            [
                {"user_id": 10, "total_amount": 12_500},
                {"user_id": 20, "total_amount": 8_000},
            ],
            "шагов",
        )

        self.assertIn("🥇 <@10> — **12,500** шагов", text)
        self.assertIn("🥈 <@20> — **8,000** шагов", text)

    def test_naive_database_datetime_is_treated_as_utc(self):
        value = _discord_datetime(datetime(2026, 10, 29, 12, 0))

        self.assertEqual(value.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
