import unittest
from types import SimpleNamespace

from app.modules.interaction_response import (
    acknowledge_slash_command_response,
    cleanup_slash_command_response,
    send_interaction_response,
)


class FakeResponse:
    def __init__(self) -> None:
        self.done = False
        self.ephemeral = None

    def is_done(self) -> bool:
        return self.done

    async def send_message(self, content: str, *, ephemeral: bool) -> None:
        self.done = True
        self.ephemeral = ephemeral
        self.content = content


class FakeInteraction:
    def __init__(self, interaction_id: int, command_name: str) -> None:
        self.id = interaction_id
        self.application_command = SimpleNamespace(name=command_name)
        self.response = FakeResponse()
        self.original_response_deleted = False
        self.edited_response = None
        self.sent_response = None
        self.followup = SimpleNamespace(send=self.send_followup)
        self.bot = None

    async def delete_original_response(self) -> None:
        self.original_response_deleted = True

    async def edit_original_response(self, *args, **kwargs):
        self.edited_response = (args, kwargs)

    async def send_followup(self, *args, **kwargs):
        self.sent_response = (args, kwargs)

    async def send(self, *args, **kwargs):
        self.sent_response = (args, kwargs)


class SlashCommandResponseTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = SimpleNamespace(
            _automatically_acknowledged_interactions=set(),
            logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
        )

    async def test_regular_command_is_deferred_and_cleaned_up(self) -> None:
        interaction = FakeInteraction(1, "leaderboard")
        interaction.bot = self.bot

        await acknowledge_slash_command_response(self.bot, interaction, "leaderboard")

        self.assertTrue(interaction.response.done)
        self.assertTrue(interaction.response.ephemeral)
        self.assertIn(interaction.id, self.bot._automatically_acknowledged_interactions)

        await cleanup_slash_command_response(self.bot, interaction, "leaderboard")

        self.assertTrue(interaction.original_response_deleted)
        self.assertNotIn(interaction.id, self.bot._automatically_acknowledged_interactions)

    async def test_modal_command_is_not_deferred(self) -> None:
        interaction = FakeInteraction(2, "anonimuska")
        interaction.bot = self.bot

        await acknowledge_slash_command_response(self.bot, interaction, "anonimuska")

        self.assertFalse(interaction.response.done)
        self.assertNotIn(interaction.id, self.bot._automatically_acknowledged_interactions)

    async def test_public_result_replaces_private_placeholder_with_followup(self) -> None:
        interaction = FakeInteraction(3, "leaderboard")
        interaction.bot = self.bot
        await acknowledge_slash_command_response(self.bot, interaction, "leaderboard")

        await send_interaction_response(interaction, "Публичный результат")

        self.assertTrue(interaction.original_response_deleted)
        self.assertEqual(interaction.sent_response, (("Публичный результат",), {}))
        self.assertNotIn(interaction.id, self.bot._automatically_acknowledged_interactions)

    async def test_private_result_edits_placeholder_and_is_not_deleted(self) -> None:
        interaction = FakeInteraction(4, "balance")
        interaction.bot = self.bot
        await acknowledge_slash_command_response(self.bot, interaction, "balance")

        await send_interaction_response(interaction, "Личный результат", ephemeral=True)

        self.assertFalse(interaction.original_response_deleted)
        self.assertEqual(interaction.edited_response, (("Личный результат",), {}))
        self.assertNotIn(interaction.id, self.bot._automatically_acknowledged_interactions)


if __name__ == "__main__":
    unittest.main()
