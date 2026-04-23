import random

import disnake
from disnake.ext import commands

from app.modules.database import Database
from app.modules.menus.giveaway import GiveawayFinishView
from app.modules.menus.recruitment import RecruitmentView
from app.modules.modals.recruitment_setup_modal import DEFAULT_RECRUITMENT_QUESTIONS
from app.modules.scripts import Scripts


class ContextInteractionAdapter:
    def __init__(self, ctx):
        self.ctx = ctx
        self.author = ctx.author
        self.channel = ctx.channel
        self.guild = ctx.guild
        self.followup = self

    async def send(self, *args, **kwargs):
        kwargs.pop("ephemeral", None)
        return await self.ctx.send(*args, **kwargs)


class PrefixCommands(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db = Database()
        self.sc = Scripts(logger, bot)

    async def cog_check(self, ctx):
        return self.bot.is_mi_user(ctx.author)

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Не хватает аргумента `{error.param.name}`. Используйте `e!help <команда>`.")
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send("Не удалось разобрать аргументы команды. Проверьте упоминания, ID и порядок параметров.")
            return

        self.logger.exception(f"Ошибка prefix-команды {ctx.command}: {error}")
        await ctx.send(f"Произошла ошибка: {error}")

    @commands.command(name="ping")
    async def ping(self, ctx):
        await ctx.send(f"Понг! {round(self.bot.latency * 1000)}мс")

    @commands.command(name="role")
    async def role(
        self,
        ctx,
        member: disnake.Member,
        role: disnake.Role,
        action: str,
    ):
        action = action.lower()
        if action not in {"add", "take", "del", "remove"}:
            await ctx.send("Действие должно быть `add` или `take`.")
            return

        try:
            if action == "add":
                await member.add_roles(role)
                await ctx.send(f"Роль {role.name} успешно добавлена участнику {member.display_name}.")
            else:
                await member.remove_roles(role)
                await ctx.send(f"Роль {role.name} успешно снята с участника {member.display_name}.")
        except disnake.errors.Forbidden:
            await ctx.send("У меня нет прав для изменения ролей.")
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/role: {e}")
            await ctx.send(f"Произошла ошибка: {e}")

    @commands.command(name="contest")
    async def contest(
        self,
        ctx,
        channel: disnake.TextChannel,
        contest_name: str,
        emoji: str,
        status: str,
        top_count: int = 10,
    ):
        status = status.lower()
        if status not in {"start", "stop"}:
            await ctx.send("Статус должен быть `start` или `stop`.")
            return

        try:
            guild_id = ctx.guild.id
            channel_id = channel.id
            is_start = status == "start"

            if is_start:
                contest = self.db.start_contest_run(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                    emoji_str=emoji,
                )
                self.db.create_update_contest(guild_id, channel_id, emoji, True)
                await ctx.send(
                    f"Конкурс `{contest.contest_name}` в канале <#{channel_id}> активирован. "
                    f"Выбранное эмодзи: {emoji}"
                )
                return

            contest = self.db.stop_contest_run(
                guild_id=guild_id,
                channel_id=channel_id,
                contest_name=contest_name,
            )
            if not contest:
                await ctx.send(f"Активный конкурс `{contest_name}` в канале <#{channel_id}> не найден.")
                return

            await self.sc.read_messages_with_reaction(
                channel_id=channel_id,
                emoji=contest.emoji_str,
                inter=ctx,
                contest_id=contest.id,
                top_count=top_count,
            )
            if not self.db.get_active_contests_for_channel(guild_id, channel_id):
                self.db.create_update_contest(guild_id, channel_id, contest.emoji_str, False)
            await ctx.send(f"Конкурс `{contest.contest_name}` в канале <#{channel_id}> завершён.")
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/contest: {e}")
            await ctx.send(f"Произошла ошибка: {e}")

    @commands.command(name="convert")
    async def convert(
        self,
        ctx,
        message_id: int,
        output_format: str = "mov",
        channel: disnake.TextChannel = None,
    ):
        output_format = output_format.lower()
        if output_format not in {"mov", "gif"}:
            await ctx.send("Формат должен быть `mov` или `gif`.")
            return

        try:
            target_channel = channel or ctx.channel
            message = await target_channel.fetch_message(message_id)
            if not message.attachments:
                await ctx.send("В этом сообщении нет вложений.")
                return

            await self.sc.process_video_conversion(
                ContextInteractionAdapter(ctx),
                message.attachments,
                output_format=output_format,
            )
        except disnake.NotFound:
            await ctx.send("Сообщение не найдено. Проверьте ID и канал.")
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/convert: {e}")
            await ctx.send(f"Произошла ошибка: {e}")

    @commands.command(name="add_statistic")
    async def add_statistic(
        self,
        ctx,
        channel: disnake.TextChannel,
        status: str,
    ):
        status = status.lower()
        if status not in {"start", "stop"}:
            await ctx.send("Статус должен быть `start` или `stop`.")
            return

        try:
            is_active = status == "start"
            self.db.create_update_channel_statistic(ctx.guild.id, channel.id, is_active)
            if is_active:
                await ctx.send(f"Отслеживание статистики в канале {channel.mention} активировано.")
            else:
                await ctx.send(f"Отслеживание статистики в канале {channel.mention} завершено.")
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/add_statistic: {e}")
            await ctx.send(f"Произошла ошибка: {e}")

    @commands.command(name="add_anonimus_channel")
    async def add_anonimus_channel(
        self,
        ctx,
        channel: disnake.TextChannel,
        action: str,
    ):
        action = action.lower()
        if action not in {"add", "del", "remove"}:
            await ctx.send("Действие должно быть `add` или `del`.")
            return

        try:
            is_active = action == "add"
            self.db.create_update_channel_anonimus(ctx.guild.id, channel.id, is_active)
            if is_active:
                await ctx.send(f"Анонимные сообщения в канале {channel.mention} активированы.")
            else:
                await ctx.send(f"Анонимные сообщения в канале {channel.mention} выключены.")
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/add_anonimus_channel: {e}")
            await ctx.send(f"Произошла ошибка: {e}")

    @commands.command(name="anonimuska")
    async def anonimuska(self, ctx, *, message: str):
        try:
            channel_id = ctx.channel.id
            anonimus_channels = self.db.get_all_anonimus_channel()
            if channel_id not in anonimus_channels:
                await ctx.send("Данный канал не поддерживает анонимные сообщения.")
                return

            embed = disnake.Embed(
                title="Анонимуська",
                description=message[:4096],
                color=0x00008B,
            )
            embed.set_author(
                name="Emiliabot",
                url="https://discord.com/api/oauth2/authorize?client_id=602393416017379328&permissions=8&scope=bot+applications.commands",
                icon_url="https://media.discordapp.net/attachments/1186903406196047954/1186903657904623637/avatar_2.png",
            )
            embed.set_footer(text="Made by the_usual_god")

            await ctx.message.delete()
            await ctx.channel.send(embed=embed)
            self.logger.info(
                f"Анонимное сообщение через prefix от {ctx.author} (ID: {ctx.author.id}) "
                f"в канале {ctx.channel} (ID: {channel_id}): {message[:100]}"
            )
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/anonimuska: {e}")
            await ctx.send(f"Произошла ошибка: {e}")

    @commands.command(name="recruitment_create")
    async def recruitment_create(
        self,
        ctx,
        requests_channel: disnake.TextChannel,
        panel_channel: disnake.TextChannel,
        *,
        positions_text: str,
    ):
        try:
            positions = self._parse_positions(positions_text)
            if not positions:
                await ctx.send("Укажите хотя бы одну должность в формате `Название|Описание`.")
                return

            self.db.create_update_recruitment_channel(ctx.guild.id, requests_channel.id)
            self.db.replace_recruitment_positions(ctx.guild.id, positions)
            if not self.db.get_recruitment_questions(ctx.guild.id):
                self.db.replace_recruitment_questions(ctx.guild.id, DEFAULT_RECRUITMENT_QUESTIONS)

            embed = disnake.Embed(
                title="Набор в команду сервера",
                description=(
                    "Выберите направление в меню ниже и заполните короткую анкету. "
                    "После отправки заявка попадёт администрации на рассмотрение."
                ),
                color=0x2F3136,
            )
            embed.add_field(
                name="Доступные направления",
                value="\n".join(
                    f"**{position['title']}** - {position['description']}"
                    for position in positions
                )[:1024],
                inline=False,
            )
            embed.set_footer(text="Заявку можно отправить через выпадающее меню")

            panel_message = await panel_channel.send(
                embed=embed,
                view=RecruitmentView(self.logger, positions),
            )
            self.db.create_update_recruitment_message(ctx.guild.id, panel_message.id)
            await ctx.send(
                f"Панель набора создана в канале {panel_channel.mention}. "
                f"Заявки будут приходить в канал {requests_channel.mention}."
            )
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/recruitment_create: {e}")
            await ctx.send(f"Произошла ошибка: {e}")

    @commands.command(name="giveaway_create")
    async def giveaway_create(
        self,
        ctx,
        channel: disnake.TextChannel,
        emoji: str,
        winner_count: int,
        *,
        description: str,
    ):
        try:
            if winner_count < 1:
                await ctx.send("Количество победителей должно быть больше нуля.")
                return

            embed = disnake.Embed(
                title="Розыгрыш",
                description=description[:4096],
                color=0x2F855A,
            )
            embed.add_field(
                name="Как участвовать",
                value=f"Нажмите реакцию {emoji} под этим сообщением.",
                inline=False,
            )
            embed.add_field(name="Количество победителей", value=str(winner_count), inline=True)
            embed.set_footer(text="Розыгрыш завершает администрация сервера")

            giveaway_message = await channel.send(embed=embed)
            await giveaway_message.add_reaction(emoji)

            giveaway = self.db.create_giveaway(
                guild_id=ctx.guild.id,
                channel_id=channel.id,
                message_id=giveaway_message.id,
                admin_channel_id=ctx.channel.id,
                creator_id=ctx.author.id,
                emoji_str=emoji,
                description=description,
                winner_count=winner_count,
            )

            admin_embed = self._build_giveaway_admin_embed(giveaway, active_count=0, left_count=0)
            admin_message = await ctx.channel.send(
                embed=admin_embed,
                view=GiveawayFinishView(self.logger),
            )
            self.db.update_giveaway_admin_message(giveaway.id, admin_message.id)
            await ctx.send(
                f"Розыгрыш создан в канале {channel.mention}. "
                f"Админ-панель отправлена в этот канал."
            )
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/giveaway_create: {e}")
            await ctx.send(f"Произошла ошибка: {e}")

    @commands.command(name="giveaway_finish")
    async def giveaway_finish(
        self,
        ctx,
        admin_message_id: int,
    ):
        try:
            giveaway = self.db.get_active_giveaway_by_admin_message(
                guild_id=ctx.guild.id,
                admin_channel_id=ctx.channel.id,
                admin_message_id=admin_message_id,
            )
            if not giveaway:
                await ctx.send("Активный розыгрыш для этой админ-панели не найден.")
                return

            channel = self.bot.get_channel(giveaway.channel_id)
            if not channel:
                await ctx.send("Не удалось найти канал с сообщением розыгрыша.")
                return

            participant_ids = await self._sync_giveaway_participants(channel, giveaway)
            winners = self._select_winners(participant_ids, giveaway.winner_count)
            giveaway = self.db.finish_giveaway(giveaway.id, winners)

            if winners:
                winners_text = "\n".join(
                    f"{place}. <@{winner_id}>"
                    for place, winner_id in enumerate(winners, start=1)
                )
                result_text = f"Розыгрыш завершён!\n\n**Победители:**\n{winners_text}"
            else:
                result_text = "Розыгрыш завершён, но участников не найдено."

            await channel.send(result_text)
            await ctx.send(f"Розыгрыш в канале {channel.mention} завершён.")
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/giveaway_finish: {e}")
            await ctx.send(f"Произошла ошибка: {e}")

    @commands.command(name="help")
    async def prefix_help(self, ctx, command_name: str = None):
        await self._send_help(ctx, command_name)

    @commands.command(name="help_command")
    async def prefix_help_command(self, ctx, command_name: str):
        await self._send_help(ctx, command_name)

    async def _send_help(self, ctx, command_name: str = None):
        help_cog = self.bot.get_cog("Help")
        if not help_cog:
            await ctx.send("Модуль справки сейчас недоступен.")
            return

        if not command_name:
            pages = help_cog._build_help_pages()
            await ctx.send(embed=pages[0])
            return

        command_info = self._get_help_command_info(command_name)
        if not command_info:
            await ctx.send("Команда не найдена в справке.")
            return

        embed = help_cog._build_embed(title=command_info["title"])
        embed.add_field(name="Тип", value=command_info["kind"], inline=False)
        embed.add_field(name="Описание", value=command_info["short"], inline=False)
        embed.add_field(
            name="Доступ",
            value="Только администрация" if command_info["admin_only"] else "Доступно всем",
            inline=False,
        )
        if command_info["params"]:
            embed.add_field(
                name="Параметры",
                value="\n".join(
                    f"**{param_name}**: {param_description}"
                    for param_name, param_description in command_info["params"]
                ),
                inline=False,
            )
        embed.add_field(
            name="Подробности",
            value="\n".join(f"- {detail}" for detail in command_info["details"]),
            inline=False,
        )
        await ctx.send(embed=embed)

    @staticmethod
    def _parse_positions(positions_text: str) -> list[dict]:
        positions = []
        for index, raw_position in enumerate(positions_text.split(";")):
            if index >= 5:
                break

            parts = [part.strip() for part in raw_position.split("|", maxsplit=1)]
            title = parts[0] if parts and parts[0] else ""
            if not title:
                continue

            description = parts[1] if len(parts) > 1 and parts[1] else "Без описания"
            positions.append({
                "title": title[:100],
                "description": description[:100],
            })

        return positions

    @staticmethod
    def _build_giveaway_admin_embed(giveaway, active_count: int, left_count: int) -> disnake.Embed:
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

    async def _sync_giveaway_participants(self, channel, giveaway) -> list[int]:
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
            if not user.bot:
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

    @staticmethod
    def _get_help_command_info(command_name: str):
        from app.modules.cogs.help_commands import COMMANDS_INFO

        normalized_name = command_name.removeprefix("/").lower()
        return COMMANDS_INFO.get(normalized_name)


def setup(bot, logger):
    bot.add_cog(PrefixCommands(bot, logger))
