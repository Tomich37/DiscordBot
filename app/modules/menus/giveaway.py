import disnake


class GiveawayFinishView(disnake.ui.View):
    def __init__(self, logger):
        self.logger = logger
        super().__init__(timeout=None)

    @disnake.ui.button(
        label="Завершить розыгрыш",
        style=disnake.ButtonStyle.danger,
        custom_id="giveaway_finish_button",
    )
    async def finish_giveaway(
        self,
        button: disnake.ui.Button,
        interaction: disnake.MessageInteraction,
    ):
        if not interaction.author.guild_permissions.administrator:
            await interaction.response.send_message(
                "Завершать розыгрыш может только администратор.",
                ephemeral=True,
            )
            return

        bot = getattr(interaction, "bot", None) or interaction.client
        cog = bot.get_cog("GiveawayCommands")
        if not cog:
            await interaction.response.send_message(
                "Модуль розыгрышей сейчас недоступен.",
                ephemeral=True,
            )
            return

        await cog.finish_giveaway_from_admin_panel(
            inter=interaction,
            admin_channel=interaction.channel,
            admin_message_id=interaction.message.id,
        )
