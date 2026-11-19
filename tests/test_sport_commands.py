import unittest
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.modules.cogs.sport_commands import (
    SportCommands,
    _daily_summary_period,
    _discord_datetime,
    _leaderboard_text,
    _progress_bar,
    _sport_entry_choice_label,
)


class SportCommandHelpersTests(unittest.TestCase):
    def test_challenge_commands_require_name_and_have_autocomplete(self):
        commands_by_name = SportCommands.sport.children

        self.assertEqual(
            [option.name for option in commands_by_name["create"].body.options],
            ["channel", "name", "unit", "target", "duration_days"],
        )
        for command_name in ("join", "add", "status", "top", "finish", "cancel"):
            option_names = [
                option.name
                for option in commands_by_name[command_name].body.options
            ]
            self.assertIn("challenge", option_names)
            self.assertIn(
                "challenge",
                commands_by_name[command_name].autocompleters,
            )

        self.assertEqual(
            [option.name for option in commands_by_name["cancel"].body.options],
            ["challenge", "entry"],
        )
        self.assertIn("entry", commands_by_name["cancel"].autocompleters)

    def test_cancel_entry_choice_contains_id_user_amount_and_local_date(self):
        label = _sport_entry_choice_label(
            {
                "id": 42,
                "user_id": 123,
                "amount": 5_000,
                "recorded_at": datetime(2026, 11, 19, 3, 30),
            },
            "шагов",
            ZoneInfo("Asia/Tomsk"),
        )

        self.assertEqual(
            label,
            "#42 · 19.11.2026 10:30 · пользователь 123 · 5,000 шагов",
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

    def test_progress_entry_embed_is_public_activity_message(self):
        challenge = {
            "activity_name": "10к шагов",
            "unit_name": "шагов",
            "target_amount": 10_000,
            "total_amount": 1_500,
        }

        embed = SportCommands._build_progress_entry_embed(
            challenge,
            user_id=123,
            amount=500,
        )

        self.assertIn("<@123>", embed.description)
        self.assertIn("500", embed.description)
        self.assertEqual(embed.fields[1].value, "**8,500** шагов")

    def test_daily_summary_contains_top_five_and_remaining_amount(self):
        challenge = {
            "activity_name": "10к шагов",
            "unit_name": "шагов",
            "target_amount": 10_000,
            "total_amount": 3_000,
        }
        rows = [
            {"user_id": user_id, "total_amount": 600 - user_id}
            for user_id in range(1, 6)
        ]

        embed = SportCommands._build_daily_summary_embed(
            challenge,
            rows,
            date(2026, 10, 29),
        )

        self.assertIn("<@1>", embed.fields[0].value)
        self.assertIn("<@5>", embed.fields[0].value)
        self.assertEqual(embed.fields[1].value, "**7,000** шагов")
        self.assertEqual(embed.footer.text, "Сводка за 29.10.2026")

    def test_daily_summary_uses_full_previous_day_after_morning_hour(self):
        local_now = datetime(2026, 10, 30, 9, 15, tzinfo=ZoneInfo("Asia/Tomsk"))

        summary_on, period_start, period_end = _daily_summary_period(local_now, 9)

        self.assertEqual(summary_on, date(2026, 10, 29))
        self.assertEqual(period_start, datetime(2026, 10, 28, 17, 0))
        self.assertEqual(period_end, datetime(2026, 10, 29, 17, 0))

    def test_daily_summary_waits_for_configured_morning_hour(self):
        local_now = datetime(2026, 10, 30, 8, 59, tzinfo=ZoneInfo("Asia/Tomsk"))

        self.assertIsNone(_daily_summary_period(local_now, 9))


if __name__ == "__main__":
    unittest.main()
