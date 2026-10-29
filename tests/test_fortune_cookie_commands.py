import asyncio
import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.modules.cogs.fortune_cookie_commands import (
    FortuneCookieCommands,
    _build_cookie_embed,
)
from app.modules.fortune_cookie_service import COOKIE_STYLE_VERSION


class FakeResponse:
    def __init__(self) -> None:
        self.done = False

    def is_done(self) -> bool:
        return self.done

    async def defer(self) -> None:
        self.done = True


class FakeDatabase:
    def __init__(self, interaction) -> None:
        self.interaction = interaction
        self.was_deferred_before_query = False

    async def get_fortune_cookie_opening(self, **kwargs):
        self.was_deferred_before_query = self.interaction.response.is_done()
        return {
            "seed": 101,
            "text": "Сегодня всё получится.",
            "rarity": "common",
            "image": "фонарь",
        }


class FortuneCookieCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_cached_style_is_replaced(self) -> None:
        cog = object.__new__(FortuneCookieCommands)
        cog.new_prediction_percent = 0

        self.assertTrue(
            cog._should_generate_prediction({"arcana": "XIX — Солнце", "style_version": 1})
        )
        self.assertFalse(
            cog._should_generate_prediction(
                {"arcana": "XIX — Солнце", "style_version": COOKIE_STYLE_VERSION}
            )
        )

    async def test_embed_shows_arcana(self) -> None:
        next_available_at = datetime(2026, 10, 30, 0, 0, tzinfo=ZoneInfo("Asia/Tomsk"))
        embed = _build_cookie_embed(
            {
                "seed": 101,
                "text": "Знакомая дорога сегодня поможет заметить новую возможность.",
                "rarity": "common",
                "image": "фонарь",
                "arcana": "XIX — Солнце",
            },
            next_available_at=next_available_at,
        )

        fields = {field.name: field.value for field in embed.fields}
        self.assertEqual(fields["Аркан"], "XIX — Солнце")
        timestamp = int(next_available_at.timestamp())
        self.assertEqual(
            fields["Следующее печенье"],
            f"Новая попытка <t:{timestamp}:R>\nСброс: <t:{timestamp}:F>",
        )

    async def test_next_attempt_starts_at_local_midnight(self) -> None:
        cog = object.__new__(FortuneCookieCommands)
        cog.timezone = ZoneInfo("Asia/Tomsk")

        next_available_at = cog._next_available_at(date(2026, 10, 29))

        self.assertEqual(
            next_available_at,
            datetime(2026, 10, 30, 0, 0, tzinfo=ZoneInfo("Asia/Tomsk")),
        )

    async def test_interaction_is_deferred_before_database_query(self) -> None:
        interaction = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            author=SimpleNamespace(id=2),
            response=FakeResponse(),
            edited_response=None,
        )

        async def edit_original_response(**kwargs):
            interaction.edited_response = kwargs

        interaction.edit_original_response = edit_original_response

        cog = object.__new__(FortuneCookieCommands)
        cog._user_locks = {}
        cog._generation_locks = {"common": asyncio.Lock()}
        cog.timezone = ZoneInfo("Asia/Tomsk")
        cog._today = lambda: date(2026, 10, 27)
        cog.db = FakeDatabase(interaction)
        cog.logger = SimpleNamespace(warning=lambda *args: None, exception=lambda *args: None)

        with patch(
            "app.modules.cogs.fortune_cookie_commands._build_cookie_embed",
            return_value="печенье",
        ):
            await FortuneCookieCommands.cookie.callback(cog, interaction)

        self.assertTrue(cog.db.was_deferred_before_query)
        self.assertEqual(interaction.edited_response, {"embed": "печенье"})


if __name__ == "__main__":
    unittest.main()
