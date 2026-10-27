import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from app.modules.cogs.prefix_commands import PrefixCommands


class FakeDatabase:
    def __init__(self) -> None:
        self.reset_arguments = None

    async def reset_fortune_cookie_opening(self, **kwargs):
        self.reset_arguments = kwargs
        return {"status": "reset", "prediction_id": 77}


class PrefixCookieResetTests(unittest.IsolatedAsyncioTestCase):
    async def test_reset_cookie_accepts_user_id(self) -> None:
        guild = SimpleNamespace(
            id=10,
            name="Тестовый сервер",
            get_member=lambda user_id: None,
        )
        ctx = SimpleNamespace(
            guild=guild,
            author=SimpleNamespace(id=20),
        )
        cog = object.__new__(PrefixCommands)
        cog.db = FakeDatabase()
        cog.cookie_timezone = ZoneInfo("Asia/Tomsk")
        cog.logger = SimpleNamespace(info=lambda *args: None, exception=lambda *args: None)
        cog._delete_source_message = AsyncMock(return_value=True)
        cog._send_dm_notice = AsyncMock()

        expected_date = datetime.now(cog.cookie_timezone).date()
        await PrefixCommands.reset_cookie.callback(cog, ctx, 123456789012345678)

        self.assertEqual(
            cog.db.reset_arguments,
            {
                "guild_id": 10,
                "user_id": 123456789012345678,
                "opened_on": expected_date,
            },
        )
        cog._send_dm_notice.assert_awaited_once_with(
            ctx,
            "Печенье пользователя ID `123456789012345678` сброшено. "
            "Теперь он может снова выполнить `/cookie`.",
        )


if __name__ == "__main__":
    unittest.main()
