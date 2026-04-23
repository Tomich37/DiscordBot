import random

import disnake
from disnake.ext import commands

from app.modules.database import Database
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

    @commands.slash_command(
        name="giveaway_finish",
        description="Завершить розыгрыш и выбрать победителей",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True),
    )
    @commands.has_permissions(administrator=True)
    async def giveaway_finish(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: disnake.TextChannel,
        message_id: str,
    ):
        """
        Завершение розыгрыша по ID сообщения.

        Parameters
        ----------
        channel: Канал, где был опубликован розыгрыш
        message_id: ID сообщения розыгрыша
        """
        try:
            await inter.response.defer(ephemeral=True)

            giveaway = self.db.get_active_giveaway_by_message(
                guild_id=inter.guild.id,
                channel_id=channel.id,
                message_id=int(message_id),
            )
            if not giveaway:
                await inter.followup.send(
                    "Активный розыгрыш с таким сообщением не найден.",
                    ephemeral=True,
                )
                return

            participant_ids = await self._sync_participants_from_reactions(channel, giveaway)
            winners = self._select_winners(participant_ids, giveaway.winner_count)
            self.db.finish_giveaway(giveaway.id, winners)

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
            await inter.followup.send(
                f"Розыгрыш в канале {channel.mention} завершён.",
                ephemeral=True,
            )
        except ValueError:
            await inter.followup.send(
                "ID сообщения должен быть числом.",
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


def setup(bot, logger):
    bot.add_cog(GiveawayCommands(bot, logger))
