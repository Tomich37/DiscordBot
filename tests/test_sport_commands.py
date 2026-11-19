import unittest
from datetime import date, datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import disnake
from PIL import Image

from app.modules.cogs.sport_commands import (
    CANCELLED_SPORT_COLOR,
    SportCommands,
    _daily_summary_period,
    _discord_datetime,
    _leaderboard_text,
    _option_snowflake_id,
    _progress_bar,
    _sport_calendar_period_end,
    _sport_entry_choice_label,
)
from app.modules.sport_activity_calendar import render_sport_activity_calendar


class SportCommandHelpersTests(unittest.TestCase):
    def test_challenge_commands_require_name_and_have_autocomplete(self):
        commands_by_name = SportCommands.sport.children

        self.assertEqual(
            [option.name for option in commands_by_name["create"].body.options],
            ["channel", "name", "unit", "target", "duration_days"],
        )
        for command_name in (
            "join",
            "add",
            "status",
            "top",
            "calendar",
            "finish",
            "cancel",
            "cancel_my",
        ):
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
            ["challenge", "user", "entry"],
        )
        self.assertEqual(
            commands_by_name["cancel"].body.options[1].type,
            disnake.OptionType.user,
        )
        self.assertIn("entry", commands_by_name["cancel"].autocompleters)
        self.assertEqual(
            [option.name for option in commands_by_name["cancel_my"].body.options],
            ["challenge", "entry"],
        )
        self.assertIn("entry", commands_by_name["cancel_my"].autocompleters)
        self.assertTrue(commands_by_name["cancel"].checks)
        self.assertFalse(commands_by_name["cancel_my"].checks)
        self.assertEqual(
            [option.name for option in commands_by_name["calendar"].body.options],
            ["challenge", "user"],
        )
        self.assertFalse(commands_by_name["calendar"].body.options[1].required)

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
            "#42 · 19.11.2026 10:30 · 5,000 шагов",
        )

    def test_autocomplete_user_id_is_read_from_raw_snowflake(self):
        self.assertEqual(_option_snowflake_id("123456789012345678"), 123456789012345678)

    def test_autocomplete_user_id_is_read_from_member_object(self):
        member = SimpleNamespace(id=123456789012345678)

        self.assertEqual(_option_snowflake_id(member), 123456789012345678)

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

    def test_cancelled_entry_embed_is_public_red_notification(self):
        challenge = {
            "activity_name": "Спим 10000 часов вместе",
            "unit_name": "часов",
            "target_amount": 10_000,
            "total_amount": 1_418,
        }
        entry = {
            "id": 42,
            "user_id": 123,
            "amount": 5,
            "recorded_at": datetime(2026, 11, 19, 3, 30),
        }

        embed = SportCommands._build_cancelled_entry_embed(
            challenge,
            entry,
            cancelled_by=456,
            reopened=False,
        )

        self.assertEqual(embed.color.value, CANCELLED_SPORT_COLOR)
        self.assertIn("<@456>", embed.description)
        self.assertIn("<@123>", embed.description)
        self.assertEqual(embed.fields[0].value, "**Спим 10000 часов вместе**")
        self.assertIn("**5 часов**", embed.fields[1].value)
        self.assertIn("**1,418 / 10,000** часов", embed.fields[2].value)
        self.assertEqual(embed.footer.text, "Фиксация #42")

    def test_self_cancelled_entry_embed_names_participant(self):
        challenge = {
            "activity_name": "10к шагов",
            "unit_name": "шагов",
            "target_amount": 10_000,
            "total_amount": 500,
        }
        entry = {
            "id": 7,
            "user_id": 123,
            "amount": 100,
            "recorded_at": datetime(2026, 11, 19, 3, 30),
        }

        embed = SportCommands._build_cancelled_entry_embed(
            challenge,
            entry,
            cancelled_by=123,
            reopened=False,
        )

        self.assertEqual(
            embed.description,
            "Участник <@123> отменил свой результат.",
        )

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

    def test_active_calendar_ends_today(self):
        challenge = {
            "status": "active",
            "ends_at": datetime(2027, 1, 1),
        }

        result = _sport_calendar_period_end(
            challenge,
            ZoneInfo("Asia/Tomsk"),
            date(2026, 11, 19),
        )

        self.assertEqual(result, date(2026, 11, 19))

    def test_finished_calendar_ends_on_local_completion_day(self):
        challenge = {
            "status": "completed",
            "finished_at": datetime(2026, 11, 18, 18, 30),
        }

        result = _sport_calendar_period_end(
            challenge,
            ZoneInfo("Asia/Tomsk"),
            date(2026, 11, 20),
        )

        self.assertEqual(result, date(2026, 11, 19))

    def test_activity_calendar_is_generated_as_png(self):
        image_data = render_sport_activity_calendar(
            {
                date(2026, 11, 18): 2_000,
                date(2026, 11, 19): 5_000,
            },
            date(2025, 11, 20),
            date(2026, 11, 19),
            "шагов",
        )

        self.assertIsInstance(image_data, BytesIO)
        with Image.open(image_data) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "RGB")
            self.assertGreaterEqual(image.width, 960)
            self.assertEqual(image.height, 292)


class FakeSportAutocompleteDatabase:
    def __init__(self) -> None:
        self.requested_user_id = None

    async def get_sport_challenge_by_name(self, **kwargs):
        return {"id": 7, "unit_name": "часов"}

    async def get_sport_progress_entries(self, **kwargs):
        self.requested_user_id = kwargs["user_id"]
        return [
            {
                "id": 42,
                "user_id": kwargs["user_id"],
                "amount": 5,
                "recorded_at": datetime(2026, 11, 19, 3, 30),
            }
        ]


class SportAutocompleteTests(unittest.IsolatedAsyncioTestCase):
    async def test_entry_autocomplete_accepts_raw_user_snowflake(self):
        cog = SportCommands.__new__(SportCommands)
        cog.db = FakeSportAutocompleteDatabase()
        cog.sport_timezone = ZoneInfo("Asia/Tomsk")
        inter = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            channel=SimpleNamespace(id=2),
            filled_options={
                "challenge": "Спим 10000 часов вместе",
                "user": "123456789012345678",
            },
        )

        choices = await cog.autocomplete_sport_entry(inter, "")

        self.assertEqual(cog.db.requested_user_id, 123456789012345678)
        self.assertEqual(
            choices,
            {"#42 · 19.11.2026 10:30 · 5 часов": "42"},
        )

    async def test_own_entry_autocomplete_uses_interaction_author(self):
        cog = SportCommands.__new__(SportCommands)
        cog.db = FakeSportAutocompleteDatabase()
        cog.sport_timezone = ZoneInfo("Asia/Tomsk")
        inter = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            channel=SimpleNamespace(id=2),
            author=SimpleNamespace(id=123456789012345678),
            filled_options={"challenge": "Спим 10000 часов вместе"},
        )

        choices = await cog.autocomplete_own_sport_entry(inter, "")

        self.assertEqual(cog.db.requested_user_id, 123456789012345678)
        self.assertEqual(
            choices,
            {"#42 · 19.11.2026 10:30 · 5 часов": "42"},
        )


if __name__ == "__main__":
    unittest.main()
