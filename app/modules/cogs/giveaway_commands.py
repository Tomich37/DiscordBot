import random

import disnake
from disnake.ext import commands

from app.modules.database import Database
from app.modules.menus.giveaway import GiveawayFinishView
from app.modules.modals.giveaway_modal import GiveawayModal


class GiveawayCommands(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db = Database()

    @commands.slash_command(
        name="giveaway_create",
        description="Создать розыгрыш через модальное окно",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True),
    )
    @commands.has_permissions(administrator=True)
    async def giveaway_create(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: disnake.TextChannel,
        emoji: str,
    ):
        """
        Создание розыгрыша в выбранном канале.

        Parameters
        ----------
        channel: Канал, где будет опубликован розыгрыш
        emoji: Эмодзи, по которой участники будут входить в розыгрыш
        """
        try:
            await inter.response.send_modal(
                GiveawayModal(
                    logger=self.logger,
                    channel_id=channel.id,
                    admin_channel_id=inter.channel.id,
                    emoji_str=emoji,
                    creator_id=inter.author.id,
                )
            )
        except Exception as e:
            await inter.response.send_message(
                f"Ошибка при открытии окна создания розыгрыша: {e}",
                ephemeral=True,
            )
            self.logger.error(f"Ошибка в giveaway_commands/giveaway_create: {e}")
            print(f"Ошибка в giveaway_commands/giveaway_create: {e}")

    async def finish_giveaway_from_admin_panel(
        self,
        inter,
        admin_channel: disnake.TextChannel,
        admin_message_id: int,
    ):
        try:
            await inter.response.defer(ephemeral=True)

            giveaway = self.db.get_active_giveaway_by_admin_message(
                guild_id=inter.guild.id,
                admin_channel_id=admin_channel.id,
                admin_message_id=admin_message_id,
            )
            if not giveaway:
                await inter.followup.send(
                    "Активный розыгрыш для этой админ-панели не найден.",
                    ephemeral=True,
                )
                return

            channel = self.bot.get_channel(giveaway.channel_id)
            if not channel:
                await inter.followup.send(
                    "Не удалось найти канал с сообщением розыгрыша.",
                    ephemeral=True,
                )
                return

            participant_ids = await self._sync_participants_from_reactions(channel, giveaway)
            winners = self._select_winners(participant_ids, giveaway.winner_count)
            giveaway = self.db.finish_giveaway(giveaway.id, winners)

            if winners:
                winners_text = "\n".join(
                    f"{place}. <@{winner_id}>"
                    for place, winner_id in enumerate(winners, start=1)
                )
                result_text = (
                    f"Розыгрыш завершён!\n\n"
                    f"**Победители:**\n{winners_text}"
                )
            else:
                result_text = "Розыгрыш завершён, но участников не найдено."

            await channel.send(result_text)
            await self._update_admin_panel(giveaway, remove_view=True)

            await inter.followup.send(
                f"Розыгрыш в канале {channel.mention} завершён.",
                ephemeral=True,
            )
        except Exception as e:
            await inter.followup.send(
                f"Ошибка при завершении розыгрыша: {e}",
                ephemeral=True,
            )
            self.logger.error(f"Ошибка в giveaway_commands/giveaway_finish: {e}")
            print(f"Ошибка в giveaway_commands/giveaway_finish: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: disnake.RawReactionActionEvent):
        await self._change_participant(payload, should_add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: disnake.RawReactionActionEvent):
        await self._change_participant(payload, should_add=False)

    async def _change_participant(
        self,
        payload: disnake.RawReactionActionEvent,
        should_add: bool,
    ):
        if payload.user_id == self.bot.user.id or not payload.guild_id:
            return
        if should_add and payload.member and payload.member.bot:
            return

        giveaway = self.db.get_active_giveaway_by_message(
            guild_id=payload.guild_id,
            channel_id=payload.channel_id,
            message_id=payload.message_id,
        )
        if not giveaway or str(payload.emoji) != giveaway.emoji_str:
            return

        if should_add:
            self.db.add_giveaway_participant(giveaway.id, payload.user_id)
        else:
            self.db.deactivate_giveaway_participant(giveaway.id, payload.user_id)
        await self._update_admin_panel(giveaway)

    async def _sync_participants_from_reactions(self, channel, giveaway) -> list[int]:
        try:
            message = await channel.fetch_message(giveaway.message_id)
        except disnake.NotFound:
            return self.db.get_active_giveaway_participant_ids(giveaway.id)

        reaction = next(
            (item for item in message.reactions if str(item.emoji) == giveaway.emoji_str),
            None,
        )
        if not reaction:
            return self.db.sync_giveaway_participants(giveaway.id, [])

        participant_ids = []
        async for user in reaction.users():
            if user.bot:
                continue

            participant_ids.append(user.id)
        return self.db.sync_giveaway_participants(giveaway.id, participant_ids)

    @staticmethod
    def _select_winners(participant_ids: list[int], winner_count: int) -> list[int]:
        unique_participants = list(dict.fromkeys(participant_ids))
        if not unique_participants:
            return []

        return random.sample(
            unique_participants,
            k=min(winner_count, len(unique_participants)),
        )

    async def _update_admin_panel(self, giveaway, remove_view: bool = False):
        if not giveaway.admin_channel_id or not giveaway.admin_message_id:
            return

        try:
            channel = self.bot.get_channel(giveaway.admin_channel_id)
            if not channel:
                return

            message = await channel.fetch_message(giveaway.admin_message_id)
            stats = self.db.get_giveaway_stats(giveaway.id)
            embed = self._build_admin_embed(
                giveaway,
                active_count=stats["active_count"],
                left_count=stats["left_count"],
            )
            await message.edit(
                embed=embed,
                view=None if remove_view else GiveawayFinishView(self.logger),
            )
        except disnake.NotFound:
            return
        except Exception as e:
            self.logger.error(f"Ошибка в giveaway_commands/_update_admin_panel: {e}")
            print(f"Ошибка в giveaway_commands/_update_admin_panel: {e}")

    @staticmethod
    def _build_admin_embed(giveaway, active_count: int, left_count: int) -> disnake.Embed:
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
        footer_text = (
            "Розыгрыш завершён"
            if not giveaway.is_active
            else "Кнопка завершения доступна администраторам"
        )
        embed.set_footer(text=footer_text)
        return embed


def setup(bot, logger):
    bot.add_view(GiveawayFinishView(logger))
    bot.add_cog(GiveawayCommands(bot, logger))
