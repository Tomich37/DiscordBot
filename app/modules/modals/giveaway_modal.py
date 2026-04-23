import disnake

from app.modules.database import Database


class GiveawayModal(disnake.ui.Modal):
    def __init__(
        self,
        logger,
        channel_id: int,
        emoji_str: str,
        creator_id: int,
    ):
        self.logger = logger
        self.channel_id = channel_id
        self.emoji_str = emoji_str.strip()
        self.creator_id = creator_id
        self.db = Database()

        components = [
            disnake.ui.TextInput(
                label="Описание розыгрыша",
                placeholder="Например: Разыгрываем Discord Nitro среди участников",
                custom_id="description",
                style=disnake.TextInputStyle.paragraph,
                max_length=4000,
            ),
            disnake.ui.TextInput(
                label="Количество победителей",
                placeholder="Например: 1",
                custom_id="winner_count",
                style=disnake.TextInputStyle.short,
                max_length=2,
            ),
        ]

        super().__init__(
            title="Создание розыгрыша",
            components=components,
            custom_id="giveaway_create_modal",
        )

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        giveaway_message = None
        try:
            description = interaction.text_values.get("description", "").strip()
            winner_count_raw = interaction.text_values.get("winner_count", "").strip()

            if not description:
                await interaction.response.send_message(
                    "Описание розыгрыша не может быть пустым.",
                    ephemeral=True,
                )
                return

            if not winner_count_raw.isdigit() or int(winner_count_raw) < 1:
                await interaction.response.send_message(
                    "Количество победителей должно быть целым числом больше нуля.",
                    ephemeral=True,
                )
                return

            winner_count = int(winner_count_raw)
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel:
                await interaction.response.send_message(
                    "Не удалось найти канал для публикации розыгрыша.",
                    ephemeral=True,
                )
                return

            embed = disnake.Embed(
                title="Розыгрыш",
                description=description[:4096],
                color=0x2F855A,
            )
            embed.add_field(
                name="Как участвовать",
                value=f"Нажмите реакцию {self.emoji_str} под этим сообщением.",
                inline=False,
            )
            embed.add_field(
                name="Количество победителей",
                value=str(winner_count),
                inline=True,
            )
            embed.set_footer(text="Розыгрыш завершает администратор командой")

            giveaway_message = await channel.send(embed=embed)
            await giveaway_message.add_reaction(self.emoji_str)

            giveaway = self.db.create_giveaway(
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                message_id=giveaway_message.id,
                creator_id=self.creator_id,
                emoji_str=self.emoji_str,
                description=description,
                winner_count=winner_count,
            )

            await interaction.response.send_message(
                f"Розыгрыш создан в канале {channel.mention}.\n"
                f"ID сообщения для завершения: `{giveaway.message_id}`",
                ephemeral=True,
            )
        except Exception as e:
            if giveaway_message:
                await giveaway_message.delete()

            self.logger.error(f"Ошибка в modals/giveaway_modal: {e}")
            print(f"Ошибка в modals/giveaway_modal: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"Ошибка при создании розыгрыша: {e}",
                    ephemeral=True,
                )
