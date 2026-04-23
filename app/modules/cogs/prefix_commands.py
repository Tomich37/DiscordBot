from datetime import date
from io import BytesIO
from pathlib import Path

import disnake
from disnake.ext import commands

from app.modules.database import Database


class PrefixCommands(commands.Cog):
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
        return lines[-line_count:]

    async def _send_logs_to_dm(self, ctx, title: str, content: str) -> None:
        try:
            if len(content) <= 1800:
                await ctx.author.send(f"**{title}**\n```text\n{content}```")
                return

            file_bytes = BytesIO(content.encode("utf-8"))
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
