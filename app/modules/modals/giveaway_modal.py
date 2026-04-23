import disnake

from app.modules.database import Database
from app.modules.menus.giveaway import GiveawayFinishView


class GiveawayModal(disnake.ui.Modal):
    def __init__(
        self,
        logger,
        channel_id: int,
        admin_channel_id: int,
        emoji_str: str,
        creator_id: int,
    ):
        self.logger = logger
        self.channel_id = channel_id
        self.admin_channel_id = admin_channel_id
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
        admin_message = None
        giveaway = None
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
            admin_channel = interaction.guild.get_channel(self.admin_channel_id)
            if not channel or not admin_channel:
                await interaction.response.send_message(
                    "Не удалось найти канал для публикации розыгрыша или админ-панели.",
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
            embed.set_footer(text="Розыгрыш завершает администрация сервера")

            giveaway_message = await channel.send(embed=embed)
            await giveaway_message.add_reaction(self.emoji_str)

            giveaway = self.db.create_giveaway(
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                message_id=giveaway_message.id,
                admin_channel_id=admin_channel.id,
                creator_id=self.creator_id,
                emoji_str=self.emoji_str,
                description=description,
                winner_count=winner_count,
            )

            admin_embed = self._build_admin_embed(giveaway, active_count=0, left_count=0)
            admin_message = await admin_channel.send(
                embed=admin_embed,
                view=GiveawayFinishView(self.logger),
            )
            self.db.update_giveaway_admin_message(giveaway.id, admin_message.id)

            await interaction.response.send_message(
                f"Розыгрыш создан в канале {channel.mention}.\n"
                f"Админ-панель отправлена в канал {admin_channel.mention}.",
                ephemeral=True,
            )
        except Exception as e:
            if giveaway:
                self.db.finish_giveaway(giveaway.id, [])
            if admin_message:
                await admin_message.delete()
            if giveaway_message:
                await giveaway_message.delete()

            self.logger.exception(f"Ошибка в modals/giveaway_modal: {e}")
            print(f"Ошибка в modals/giveaway_modal: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"Ошибка при создании розыгрыша: {e}",
                    ephemeral=True,
                )

    def _build_admin_embed(self, giveaway, active_count: int, left_count: int) -> disnake.Embed:
        embed = disnake.Embed(
            title="Админ-панель розыгрыша",
            description=giveaway.description[:4096],
            color=0x2F855A,
        )
        embed.add_field(
            name="Публикация",
            value=f"<#{giveaway.channel_id}> | [перейти](https://discord.com/channels/{giveaway.guild_id}/{giveaway.channel_id}/{giveaway.message_id})",
            inline=False,
        )
        embed.add_field(name="Эмодзи участия", value=giveaway.emoji_str, inline=True)
        embed.add_field(name="Победителей", value=str(giveaway.winner_count), inline=True)
        embed.add_field(name="Участвуют", value=str(active_count), inline=True)
        embed.add_field(name="Передумали", value=str(left_count), inline=True)
        embed.set_footer(text="Кнопка завершения доступна администраторам")
        return embed
