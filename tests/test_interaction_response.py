import unittest
from types import SimpleNamespace

from app.modules.interaction_response import (
    acknowledge_slash_command,
    send_interaction_response,
)


class FakeResponse:
    def __init__(self) -> None:
        self.done = False
        self.ephemeral = None

    def is_done(self) -> bool:
        return self.done

    async def defer(self, *, ephemeral: bool) -> None:
        self.done = True
        self.ephemeral = ephemeral


class FakeInteraction:
    def __init__(self, interaction_id: int) -> None:
        self.id = interaction_id
        self.response = FakeResponse()
        self.bot = None
        self.edited_response = None
        self.sent_response = None
        self.calls = []
        self.followup = SimpleNamespace(send=self.send_followup)

    async def edit_original_response(self, *args, **kwargs):
        self.calls.append("edit")
        self.edited_response = (args, kwargs)

    async def send_followup(self, *args, **kwargs):
        self.calls.append("followup")
        self.sent_response = (args, kwargs)

    async def send(self, *args, **kwargs):
        self.sent_response = (args, kwargs)


class InteractionResponseTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = SimpleNamespace(_deferred_interactions={})

    async def test_regular_command_is_acknowledged_before_callback_work(self) -> None:
        interaction = FakeInteraction(1)

        await acknowledge_slash_command(self.bot, interaction, "leaderboard")

        self.assertTrue(interaction.response.done)
        self.assertFalse(interaction.response.ephemeral)
        self.assertEqual(self.bot._deferred_interactions[interaction.id], False)

    async def test_personal_command_is_acknowledged_ephemerally(self) -> None:
        interaction = FakeInteraction(4)

        await acknowledge_slash_command(self.bot, interaction, "balance")

        self.assertTrue(interaction.response.done)
        self.assertTrue(interaction.response.ephemeral)

    async def test_modal_command_is_not_acknowledged_before_modal(self) -> None:
        interaction = FakeInteraction(5)

        await acknowledge_slash_command(self.bot, interaction, "anonimuska")

        self.assertFalse(interaction.response.done)

    async def test_public_deferred_response_edits_original_command(self) -> None:
        interaction = FakeInteraction(2)
        interaction.bot = self.bot

        await acknowledge_slash_command(self.bot, interaction, "leaderboard")
        await send_interaction_response(
            interaction,
            "Лидерборд",
            embed="embed",
        )

        self.assertTrue(interaction.response.done)
        self.assertFalse(interaction.response.ephemeral)
        self.assertEqual(
            interaction.edited_response,
            (("Лидерборд",), {"embed": "embed"}),
        )
        self.assertIsNone(interaction.sent_response)
        self.assertNotIn(interaction.id, self.bot._deferred_interactions)

    async def test_fast_response_keeps_standard_interaction_send(self) -> None:
        interaction = FakeInteraction(3)
        interaction.bot = self.bot

        await send_interaction_response(interaction, "Понг!")

        self.assertEqual(interaction.sent_response, (("Понг!",), {}))
        self.assertIsNone(interaction.edited_response)

    async def test_private_result_after_public_defer_is_sent_privately_after_ack_edit(self) -> None:
        interaction = FakeInteraction(6)
        interaction.bot = self.bot
        await acknowledge_slash_command(self.bot, interaction, "leaderboard")

        await send_interaction_response(interaction, "Личная ошибка", ephemeral=True)

        self.assertEqual(interaction.calls, ["edit", "followup"])
        self.assertEqual(
            interaction.edited_response,
            ((), {
                "content": "Запрос обработан. Подробности доступны только вам.",
                "embed": None,
                "view": None,
            }),
        )
        self.assertEqual(
            interaction.sent_response,
            (("Личная ошибка",), {"ephemeral": True}),
        )


if __name__ == "__main__":
    unittest.main()
