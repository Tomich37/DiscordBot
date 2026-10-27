import asyncio
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.cogs.fortune_cookie_commands import FortuneCookieCommands


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
