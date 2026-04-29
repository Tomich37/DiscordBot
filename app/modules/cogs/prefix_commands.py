from datetime import date
from io import BytesIO
from pathlib import Path

import disnake
from disnake.ext import commands

from app.modules.database import Database
from app.modules.logger import fix_text_mojibake


class PrefixCommands(commands.Cog):
    EXPORT_FILE_MAX_BYTES = 7 * 1024 * 1024
    EXPORT_PROGRESS_INTERVAL_MESSAGES = 1000

    LOG_TYPES = {
        "info": "info",
        "tech": "technical",
        "technical": "technical",
    }

    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db = Database()

    async def cog_check(self, ctx):
        return self.bot.is_mi_user(ctx.author)

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            return

        await self._delete_source_message(ctx)
        if isinstance(error, commands.MissingRequiredArgument):
            await self._send_dm_notice(
                ctx,
                f"Не хватает аргумента `{error.param.name}`.",
            )
            return

        if isinstance(error, commands.BadArgument):
            await self._send_dm_notice(
                ctx,
                "Не удалось разобрать аргументы команды. Проверьте упоминания, ID и порядок параметров.",
            )
            return

        self.logger.exception(f"Ошибка prefix-команды {ctx.command}: {error}")
        await self._send_dm_notice(ctx, f"Произошла ошибка: {error}")

    @commands.command(name="anon")
    async def anon(self, ctx, *, message: str):
        if not await self._delete_source_message(ctx):
            return
        try:
            sent_message = await ctx.channel.send(message[:2000])
            await self._send_action_notice(
                ctx,
                f"Анонимное сообщение отправлено в {self._format_channel_for_notice(ctx.channel)}. "
                f"ID сообщения: `{sent_message.id}`.",
            )
            self.logger.info(
                f"Анонимное сообщение через e!anon от {ctx.author} (ID: {ctx.author.id}) "
                f"в канале {ctx.channel} (ID: {ctx.channel.id}): {message[:100]}"
            )
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/anon: {e}")
            await self._send_action_notice(ctx, f"Не удалось отправить анонимное сообщение: {e}", force=True)

    @commands.command(name="help")
    async def help(self, ctx):
        if not await self._delete_source_message(ctx):
            return

        help_text = (
            "**Prefix-команды только для тебя**\n"
            "\n"
            "Пользовательские слэш-команды смотри через `/help`. Подробности по конкретной команде — через `/help_command`.\n"
            "\n"
            "`e!anon текст сообщения`\n"
            "Отправляет обычное сообщение от имени бота в текущий канал.\n"
            "Пример: `e!anon Всем привет, это сообщение от бота`\n"
            "\n"
            "`e!stat #канал on`\n"
            "`e!stat #канал off`\n"
            "Включает или выключает сбор статистики для канала.\n"
            "Пример: `e!stat #общий on`\n"
            "\n"
            "`e!role @участник @роль add`\n"
            "`e!role @участник @роль take`\n"
            "Выдаёт или снимает роль.\n"
            "Пример: `e!role @User @Moderator add`\n"
            "\n"
            "`e!logs`\n"
            "Отправляет последние 3 строки info и tech логов за сегодня.\n"
            "\n"
            "`e!logs info 45`\n"
            "`e!logs tech 30`\n"
            "Отправляет указанное количество строк выбранного лога.\n"
            "\n"
            "`e!alchemy_balance ID_пользователя количество`\n"
            "Начисляет валюту алхимии пользователю по ID на текущем сервере.\n"
            "Пример: `e!alchemy_balance 123456789012345678 50`\n"
            "\n"
            "`e!servers`\n"
            "Показывает серверы, где установлен бот, и уже существующую ссылку, если бот может её прочитать.\n"
            "\n"
            "`e!channels`\n"
            "`e!channels ID_сервера`\n"
            "Показывает текстовые и голосовые каналы сервера с их ID. В ЛС нужно указать ID сервера.\n"
            "\n"
            "`e!history ID_сервера ID_канала [количество]`\n"
            "Выгружает историю текстового или голосового канала в UTF-8 файл от новых сообщений к старым. Если количество не указано, выгружает всю доступную историю.\n"
            "\n"
            "Все команды сначала удаляют твоё сообщение, затем отправляют результат в ЛС."
        )
        await self._send_dm_notice(ctx, help_text)

    @commands.command(name="stat")
    async def stat(
        self,
        ctx,
        channel: disnake.TextChannel,
        status: str,
    ):
        if not await self._delete_source_message(ctx):
            return
        if ctx.guild is None:
            await self._send_action_notice(ctx, "Команда `e!stat` работает только на сервере.", force=True)
            return

        status = status.lower()
        if status not in {"start", "on", "enable", "stop", "off", "disable"}:
            await self._send_action_notice(ctx, "Статус должен быть `start/on` или `stop/off`.", force=True)
            return

        try:
            is_active = status in {"start", "on", "enable"}
            self.db.create_update_channel_statistic(ctx.guild.id, channel.id, is_active)
            if is_active:
                await self._send_action_notice(ctx, f"Статистика включена для канала {channel.mention}.")
            else:
                await self._send_action_notice(ctx, f"Статистика выключена для канала {channel.mention}.")
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/stat: {e}")
            await self._send_action_notice(ctx, f"Не удалось изменить статистику канала: {e}", force=True)

    @commands.command(name="role")
    async def role(
        self,
        ctx,
        member: disnake.Member,
        role: disnake.Role,
        action: str,
    ):
        if not await self._delete_source_message(ctx):
            return
        if ctx.guild is None:
            await self._send_action_notice(ctx, "Команда `e!role` работает только на сервере.", force=True)
            return

        action = action.lower()
        if action not in {"add", "give", "take", "remove", "del"}:
            await self._send_action_notice(ctx, "Действие должно быть `add` или `take`.", force=True)
            return

        try:
            if action in {"add", "give"}:
                await member.add_roles(role)
                await self._send_action_notice(
                    ctx,
                    f"Роль `{role.name}` выдана участнику `{member.display_name}`.",
                )
            else:
                await member.remove_roles(role)
                await self._send_action_notice(
                    ctx,
                    f"Роль `{role.name}` снята с участника `{member.display_name}`.",
                )
        except disnake.Forbidden:
            await self._send_action_notice(ctx, "У бота нет прав для изменения этой роли.", force=True)
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/role: {e}")
            await self._send_action_notice(ctx, f"Не удалось изменить роль: {e}", force=True)

    @commands.command(name="alchemy_balance", aliases=["alchemy_money", "money"])
    async def alchemy_balance(self, ctx, user_id: int, amount: int):
        if not await self._delete_source_message(ctx):
            return
        if ctx.guild is None:
            await self._send_dm_notice(ctx, "Команда работает только на сервере: `e!alchemy_balance ID_пользователя количество`.")
            return
        if amount <= 0:
            await self._send_dm_notice(ctx, "Количество средств должно быть положительным числом.")
            return

        try:
            result = self.db.grant_alchemy_currency(
                guild_id=ctx.guild.id,
                user_id=user_id,
                amount=amount,
            )
            if result["status"] == "not_started":
                await self._send_dm_notice(
                    ctx,
                    f"У пользователя с ID `{user_id}` нет профиля алхимии на сервере `{ctx.guild.name}`. "
                    "Сначала он должен выполнить `/alchemy_start`.",
                )
                return

            member = ctx.guild.get_member(user_id)
            target_name = f"`{member.display_name}`" if member else f"ID `{user_id}`"
            await self._send_dm_notice(
                ctx,
                f"Начислено `{amount}` валюты пользователю {target_name}. "
                f"Новый баланс: `{result['balance']}`.",
            )
            self.logger.info(
                f"Админское начисление алхимической валюты: author={ctx.author.id} "
                f"guild={ctx.guild.id} user={user_id} amount={amount} balance={result['balance']}"
            )
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/alchemy_balance: {e}")
            await self._send_dm_notice(ctx, f"Не удалось начислить валюту: {e}")

    @commands.command(name="logs")
    async def logs(self, ctx, log_type: str = None, line_count: int = 3):
        if not await self._delete_source_message(ctx):
            return
        if not log_type:
            await self._send_log_lines(ctx, "info", 3)
            await self._send_log_lines(ctx, "technical", 3)
            return

        log_prefix = self.LOG_TYPES.get(log_type.lower())
        if not log_prefix:
            await ctx.author.send("Тип логов должен быть `info` или `tech`.")
            return

        line_count = max(1, min(line_count, 300))
        await self._send_log_lines(ctx, log_prefix, line_count)

    @commands.command(name="servers")
    async def servers(self, ctx):
        if not await self._delete_source_message(ctx):
            return

        guilds = sorted(self.bot.guilds, key=lambda guild: guild.name.casefold())
        if not guilds:
            await self._send_dm_notice(ctx, "Бот сейчас не видит ни одного сервера.")
            return

        lines = [
            f"**Серверы, где установлен бот: {len(guilds)}**",
            "Команда не создаёт приглашения, а только читает уже существующие ссылки, если хватает прав.",
            "",
        ]

        for index, guild in enumerate(guilds, start=1):
            invite_text = await self._get_existing_guild_invite_text(guild)
            lines.extend(
                [
                    f"**{index}. {guild.name}**",
                    f"ID: `{guild.id}`",
                    f"Участников: `{guild.member_count or 'неизвестно'}`",
                    f"Владелец: {self._format_guild_owner_for_notice(guild)}",
                    f"Ссылка: {invite_text}",
                    "",
                ]
            )

        await self._send_long_dm_notice(ctx, "\n".join(lines).strip())

    @commands.command(name="channels")
    async def channels(self, ctx, guild_id: int = None):
        if not await self._delete_source_message(ctx):
            return

        guild = await self._get_guild_for_channels_command(ctx, guild_id)
        if not guild:
            return

        lines = [
            f"**Каналы сервера `{guild.name}`**",
            f"ID сервера: `{guild.id}`",
            "",
            "**Текстовые каналы**",
        ]

        if guild.text_channels:
            lines.extend(self._format_channels_for_notice(guild.text_channels))
        else:
            lines.append("Нет текстовых каналов.")

        lines.extend(["", "**Голосовые каналы**"])
        if guild.voice_channels:
            lines.extend(self._format_channels_for_notice(guild.voice_channels))
        else:
            lines.append("Нет голосовых каналов.")

        await self._send_long_dm_notice(ctx, "\n".join(lines).strip())

    async def _get_guild_for_channels_command(self, ctx, guild_id: int = None):
        if guild_id is None and ctx.guild is not None:
            return ctx.guild

        if guild_id is None:
            await self._send_dm_notice(ctx, "В ЛС нужно указать ID сервера: `e!channels ID_сервера`.")
            return None

        guild = self.bot.get_guild(guild_id)
        if guild:
            return guild

        await self._send_dm_notice(ctx, f"Бот не видит сервер с ID `{guild_id}`. Проверь ID через `e!servers`.")
        return None

    @staticmethod
    def _format_channels_for_notice(channels) -> list[str]:
        return [
            f"• `{channel.name}` — `{channel.id}`"
            for channel in sorted(channels, key=lambda channel: channel.position)
        ]

    @commands.command(name="history")
    async def history(self, ctx, guild_id: int, channel_id: int, limit: int = None):
        if not await self._delete_source_message(ctx):
            return
        if limit is not None and limit <= 0:
            await self._send_dm_notice(ctx, "Глубина выгрузки должна быть положительным числом.")
            return

        channel = await self._get_history_channel(ctx, guild_id, channel_id)
        if not channel:
            return

        depth_text = "вся доступная история" if limit is None else f"{limit} сообщений"
        await self._send_dm_notice(
            ctx,
            f"Начинаю выгрузку канала `#{channel.name}` (`{channel.id}`). Глубина: {depth_text}.",
        )

        try:
            total_messages, file_count = await self._export_channel_history(ctx, channel, limit)
        except disnake.Forbidden:
            await self._send_dm_notice(ctx, "Не удалось прочитать историю: у бота нет нужных прав в канале.")
            return
        except disnake.HTTPException as e:
            self.logger.exception(f"Ошибка Discord API при выгрузке истории канала {channel_id}: {e}")
            await self._send_dm_notice(ctx, f"Discord API вернул ошибку при выгрузке истории: `{e}`")
            return
        except Exception as e:
            self.logger.exception(f"Ошибка в prefix_commands/history: {e}")
            await self._send_dm_notice(ctx, f"Не удалось выгрузить историю канала: {e}")
            return

        await self._send_dm_notice(
            ctx,
            f"Выгрузка завершена. Сообщений: `{total_messages}`. Файлов отправлено: `{file_count}`.",
        )

    async def _get_history_channel(self, ctx, guild_id: int, channel_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await self._send_dm_notice(ctx, f"Бот не видит сервер с ID `{guild_id}`. Проверь ID через `e!servers`.")
            return None

        channel = guild.get_channel(channel_id)
        if not channel:
            await self._send_dm_notice(ctx, f"На сервере `{guild.name}` не найден канал с ID `{channel_id}`.")
            return None

        if not hasattr(channel, "history"):
            await self._send_dm_notice(
                ctx,
                f"Канал `#{channel.name}` найден, но текущая версия библиотеки не умеет читать историю этого типа канала.",
            )
            return None

        bot_member = guild.me or guild.get_member(self.bot.user.id)
        if not bot_member:
            await self._send_dm_notice(ctx, "Не удалось проверить права бота на сервере.")
            return None

        permissions = channel.permissions_for(bot_member)
        if not permissions.view_channel or not getattr(permissions, "read_message_history", False):
            await self._send_dm_notice(
                ctx,
                "У бота нет прав `Просматривать канал` или `Читать историю сообщений` в этом канале.",
            )
            return None

        return channel

    async def _export_channel_history(self, ctx, channel, limit: int = None) -> tuple[int, int]:
        total_messages = 0
        file_count = 0
        part_number = 1
        part_messages = 0
        buffer = self._create_history_export_buffer(channel, part_number)

        async for message in channel.history(limit=limit, oldest_first=False):
            record = self._format_message_for_history_export(message)
            encoded_record = record.encode("utf-8")

            if part_messages and buffer.tell() + len(encoded_record) > self.EXPORT_FILE_MAX_BYTES:
                file_count += 1
                await self._send_history_export_file(ctx, buffer, channel, part_number)
                part_number += 1
                part_messages = 0
                buffer = self._create_history_export_buffer(channel, part_number)

            buffer.write(encoded_record)
            total_messages += 1
            part_messages += 1

            if total_messages % self.EXPORT_PROGRESS_INTERVAL_MESSAGES == 0:
                await self._send_dm_notice(ctx, f"Выгружено сообщений: `{total_messages}`.")

        if part_messages or total_messages == 0:
            file_count += 1
            if total_messages == 0:
                buffer.write("Сообщений в выбранной глубине не найдено.\n".encode("utf-8"))
            await self._send_history_export_file(ctx, buffer, channel, part_number)

        return total_messages, file_count

    def _create_history_export_buffer(self, channel, part_number: int) -> BytesIO:
        buffer = BytesIO()
        buffer.write("\ufeff".encode("utf-8"))
        header = (
            f"Выгрузка истории канала #{channel.name}\n"
            f"Кодировка файла: UTF-8\n"
            f"Порядок сообщений: от новых к старым\n"
            f"ID сервера: {channel.guild.id}\n"
            f"Сервер: {channel.guild.name}\n"
            f"ID канала: {channel.id}\n"
            f"Часть: {part_number}\n"
            f"Медиафайлы не скачиваются, в выгрузку попадают только ссылки на них.\n"
            "\n"
        )
        buffer.write(header.encode("utf-8"))
        return buffer

    async def _send_history_export_file(
        self,
        ctx,
        buffer: BytesIO,
        channel,
        part_number: int,
    ) -> None:
        buffer.seek(0)
        filename = f"history_{channel.guild.id}_{channel.id}_part_{part_number}.txt"
        await ctx.author.send(
            content=f"Выгрузка `#{channel.name}`, часть `{part_number}`.",
            file=disnake.File(buffer, filename=filename),
        )

    def _format_message_for_history_export(self, message: disnake.Message) -> str:
        created_at = message.created_at.strftime("%Y-%m-%d %H:%M:%S %Z")
        author = self._format_message_author_for_history_export(message)
        content = message.content or ""
        lines = [
            f"Время: {created_at}",
            f"Автор: {author}",
        ]

        if message.reference and message.reference.message_id:
            lines.append(f"Ответ на сообщение: {message.reference.message_id}")

        lines.append("Текст:")
        lines.append(content if content else "[без текста]")

        media_links = self._collect_message_media_links(message)
        if media_links:
            lines.append("Медиа и вложения:")
            lines.extend(f"- {link}" for link in media_links)

        if message.embeds:
            lines.append("Embeds:")
            lines.extend(self._format_embed_for_history_export(embed) for embed in message.embeds)

        lines.extend(["", "-" * 80, ""])
        return "\n".join(lines)

    @staticmethod
    def _format_message_author_for_history_export(message: disnake.Message) -> str:
        author = message.author
        server_name = getattr(author, "display_name", None) or getattr(author, "name", str(author))
        global_tag = str(author)
        return f"{server_name} ({global_tag})"

    @staticmethod
    def _collect_message_media_links(message: disnake.Message) -> list[str]:
        links = [attachment.url for attachment in message.attachments]

        for sticker in getattr(message, "stickers", []):
            sticker_url = getattr(sticker, "url", None)
            if sticker_url:
                links.append(sticker_url)

        for embed in message.embeds:
            for asset_name in ("image", "thumbnail", "video"):
                asset = getattr(embed, asset_name, None)
                asset_url = getattr(asset, "url", None)
                if asset_url:
                    links.append(asset_url)

        return links

    @staticmethod
    def _format_embed_for_history_export(embed: disnake.Embed) -> str:
        parts = []
        if embed.title:
            parts.append(f"title={embed.title}")
        if embed.description:
            parts.append(f"description={embed.description}")
        if embed.url:
            parts.append(f"url={embed.url}")

        return "; ".join(parts) if parts else "[embed без текстовых данных]"

    async def _get_existing_guild_invite_text(self, guild: disnake.Guild) -> str:
        vanity_code = getattr(guild, "vanity_url_code", None)
        if vanity_code:
            return f"https://discord.gg/{vanity_code} (публичная vanity-ссылка)"

        bot_member = guild.me or guild.get_member(self.bot.user.id)
        if not bot_member:
            return "не удалось проверить: бот не найден в кэше сервера"

        if not bot_member.guild_permissions.manage_guild:
            return "не удалось прочитать: нужно право `Управлять сервером`"

        try:
            invites = await guild.invites()
        except disnake.Forbidden:
            return "не удалось прочитать: у бота нет права `Управлять сервером`"
        except disnake.HTTPException as e:
            self.logger.warning(f"Не удалось прочитать приглашения сервера {guild.name} (ID: {guild.id}): {e}")
            return f"не удалось прочитать: ошибка Discord API `{e}`"

        if not invites:
            return "активных приглашений нет"

        invite = self._select_invite_for_notice(invites)
        return self._format_invite_for_notice(invite)

    @staticmethod
    def _select_invite_for_notice(invites: list[disnake.Invite]) -> disnake.Invite:
        return sorted(
            invites,
            key=lambda invite: (
                bool(getattr(invite, "max_age", 0)),
                bool(getattr(invite, "max_uses", 0)),
                -(getattr(invite, "uses", 0) or 0),
            ),
        )[0]

    @staticmethod
    def _format_invite_for_notice(invite: disnake.Invite) -> str:
        parts = [invite.url]

        channel = getattr(invite, "channel", None)
        if channel:
            parts.append(f"канал: `#{channel.name}`")

        max_age = getattr(invite, "max_age", 0) or 0
        max_uses = getattr(invite, "max_uses", 0) or 0
        if max_age == 0:
            parts.append("без срока")
        if max_uses == 0:
            parts.append("без лимита использований")

        return " | ".join(parts)

    @staticmethod
    def _format_guild_owner_for_notice(guild: disnake.Guild) -> str:
        owner = guild.owner
        if owner:
            return f"`{owner}` (`{owner.id}`)"

        return f"`ID: {guild.owner_id}`"

    async def _send_log_lines(self, ctx, log_prefix: str, line_count: int) -> None:
        log_file = self._get_today_log_file(log_prefix)
        if not log_file.exists():
            await ctx.author.send(f"Лог за текущий день ещё не создан: `{log_file.name}`.")
            return

        lines = self._read_last_lines(log_file, line_count)
        if not lines:
            await ctx.author.send(f"В файле `{log_file.name}` пока нет записей.")
            return

        title = f"{log_file.name}: последние {len(lines)} строк"
        content = "".join(lines)
        await self._send_logs_to_dm(ctx, title, content)

    @staticmethod
    def _get_today_log_file(log_prefix: str) -> Path:
        logs_dir = Path(__file__).resolve().parents[1] / "logs"
        return logs_dir / f"{log_prefix}_{date.today():%Y-%m-%d}.log"

    @staticmethod
    def _read_last_lines(log_file: Path, line_count: int) -> list[str]:
        with log_file.open("r", encoding="utf-8") as file:
            lines = file.readlines()
        return [fix_text_mojibake(line) for line in lines[-line_count:]]

    async def _send_logs_to_dm(self, ctx, title: str, content: str) -> None:
        try:
            if len(content) <= 1800:
                await ctx.author.send(f"**{title}**\n```text\n{content}```")
                return

            # BOM помогает Discord и редакторам безошибочно распознать UTF-8 в предпросмотре файла.
            file_bytes = BytesIO(content.encode("utf-8-sig"))
            file_bytes.seek(0)
            await ctx.author.send(
                content=f"**{title}**",
                file=disnake.File(file_bytes, filename="logs.txt"),
            )
        except disnake.Forbidden:
            self.logger.warning(
                f"Не удалось отправить логи в ЛС пользователю {ctx.author} (ID: {ctx.author.id})."
            )

    async def _delete_source_message(self, ctx) -> bool:
        if ctx.guild is None:
            return True

        try:
            await ctx.message.delete()
            return True
        except disnake.NotFound:
            return True
        except disnake.Forbidden:
            await self._send_dm_notice(
                ctx,
                "Не смог удалить командное сообщение. Проверьте, что у бота есть право `Управлять сообщениями`.",
            )
            return False
        except Exception as e:
            self.logger.exception(f"Ошибка при удалении prefix-команды: {e}")
            await self._send_dm_notice(ctx, f"Не смог удалить командное сообщение: {e}")
            return False

    async def _send_action_notice(self, ctx, message: str, *, force: bool = False) -> None:
        if ctx.guild is None and not force:
            return

        await self._send_dm_notice(ctx, message)

    async def _send_long_dm_notice(self, ctx, message: str) -> None:
        parts = []
        current_part = ""

        for line in message.splitlines():
            next_part = f"{current_part}\n{line}" if current_part else line
            if len(next_part) > 1900:
                parts.append(current_part)
                current_part = line
            else:
                current_part = next_part

        if current_part:
            parts.append(current_part)

        for part in parts:
            await self._send_dm_notice(ctx, part)

    @staticmethod
    def _format_channel_for_notice(channel) -> str:
        mention = getattr(channel, "mention", None)
        if mention:
            return f"канал {mention}"

        return "личные сообщения"

    async def _send_dm_notice(self, ctx, message: str) -> None:
        try:
            await ctx.author.send(message)
        except disnake.Forbidden:
            self.logger.warning(
                f"Не удалось отправить ЛС пользователю {ctx.author} (ID: {ctx.author.id})."
            )


def setup(bot, logger):
    bot.add_cog(PrefixCommands(bot, logger))
