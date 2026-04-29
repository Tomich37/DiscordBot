import asyncio
import os
import importlib
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import disnake
from disnake.ext import commands
from disnake import ApplicationCommandInteraction

from app.modules.logger import SetLogs
from app.modules.database import Database
from app.modules.messages import Messages
from app.modules.scripts import Scripts

load_dotenv()
TEST_TOKEN = os.getenv('DISCORD_TEST_TOKEN')
MAIN_TOKEN = os.getenv('DISCORD_MAIN_TOKEN')
MI_ID = os.getenv('MI_ID')
logger = SetLogs().logger
ORIGINAL_HAS_PERMISSIONS = commands.has_permissions


def _parse_mi_id(value):
    try:
        return int(value) if value else None
    except ValueError:
        logger.warning("MI_ID должен быть числом. Проверьте значение в .env.")
        return None


MI_USER_ID = _parse_mi_id(MI_ID)


def _short_text(value, limit=250):
    text = str(value).replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _format_user(user):
    if not user:
        return "пользователь: неизвестен"
    return f"пользователь: {user} (ID: {user.id})"


def _format_guild(guild):
    if not guild:
        return "сервер: личные сообщения"
    return f"сервер: {guild.name} (ID: {guild.id})"


def _format_channel(channel):
    if not channel:
        return "канал: неизвестен"
    channel_name = getattr(channel, "name", str(channel))
    return f"канал: {channel_name} (ID: {channel.id})"


def _format_interaction_options(inter):
    options = getattr(inter, "filled_options", None)
    if not options:
        return "параметры: нет"
    options_text = ", ".join(f"{key}={_short_text(value, 100)}" for key, value in options.items())
    return f"параметры: {options_text}"


def _interaction_name(inter):
    command = getattr(inter, "application_command", None)
    if command and getattr(command, "name", None):
        return command.name

    data = getattr(inter, "data", None)
    if data and getattr(data, "name", None):
        return data.name
    if data and getattr(data, "custom_id", None):
        return data.custom_id

    return "неизвестно"


async def send_interaction_message(inter, *args, **kwargs):
    if inter.response.is_done():
        return await inter.followup.send(*args, **kwargs)
    return await inter.response.send_message(*args, **kwargs)


def _is_mi_user(target) -> bool:
    user = getattr(target, "author", None) or getattr(target, "user", None)
    return bool(MI_USER_ID and user and user.id == MI_USER_ID)


def _patch_has_permissions_for_mi():
    def has_permissions_with_mi_access(**perms):
        original_decorator = ORIGINAL_HAS_PERMISSIONS(**perms)

        def decorator(func):
            async def predicate(ctx):
                if _is_mi_user(ctx):
                    return True

                permissions = ctx.permissions if isinstance(ctx, disnake.Interaction) else ctx.channel.permissions_for(
                    ctx.author,
                    ignore_timeout=False,
                )
                missing = [
                    perm
                    for perm, value in perms.items()
                    if getattr(permissions, perm) != value
                ]
                if not missing:
                    return True

                raise commands.MissingPermissions(missing)

            return commands.check(predicate)(func)

        if MI_USER_ID:
            return decorator
        return original_decorator

    commands.has_permissions = has_permissions_with_mi_access


_patch_has_permissions_for_mi()


class Bot(commands.Bot):
    USER_STATS_FLUSH_INTERVAL_SECONDS = 30

    def __init__(self, logger):
        super().__init__(
            command_prefix=commands.when_mentioned_or("e!"),
            intents=disnake.Intents().all(),
            case_insensitive=True,
            command_sync_flags=commands.CommandSyncFlags.default(),
            help_command=None,
        )
        self.logger = logger
        self.scripts = Scripts(logger, self)
        self.db = Database()
        self.scheduler = AsyncIOScheduler()
        self.mi_user_id = MI_USER_ID
        self.user_message_counters = defaultdict(int)
        self.user_message_counters_lock = asyncio.Lock()
        self.user_stats_flush_task = None

    def is_mi_user(self, user) -> bool:
        return bool(self.mi_user_id and user and user.id == self.mi_user_id)

    def log_user_action(self, action, inter, details=None):
        parts = [
            action,
            _format_user(getattr(inter, "author", None) or getattr(inter, "user", None)),
            _format_guild(getattr(inter, "guild", None)),
            _format_channel(getattr(inter, "channel", None)),
        ]
        if details:
            parts.append(details)
        self.logger.info(" | ".join(parts))

    async def on_ready(self):
        if not hasattr(self, "scheduler_running"):
            self.scheduler.add_job(
                self.scripts.send_daily_statistics,
                "cron",
                hour=0,
                minute=0,
                misfire_grace_time=60
            )
            self.scheduler.start()
            self.scheduler_running = True
        if not hasattr(self, "voice_sessions_initialized"):
            self._initialize_active_voice_sessions()
            self.voice_sessions_initialized = True
        if not self.user_stats_flush_task or self.user_stats_flush_task.done():
            self.user_stats_flush_task = asyncio.create_task(self._flush_user_stats_loop())
        print(f"Logged in as {self.user}")
        print("------")
        self.logger.debug(f"Бот запущен как {self.user} (ID: {self.user.id})")

    async def close(self):
        if self.user_stats_flush_task:
            self.user_stats_flush_task.cancel()
            try:
                await self.user_stats_flush_task
            except asyncio.CancelledError:
                pass

        await self.flush_user_message_stats()
        await super().close()

    async def queue_user_message_stat(self, guild_id: int, user_id: int):
        async with self.user_message_counters_lock:
            self.user_message_counters[(guild_id, user_id)] += 1

    async def get_pending_user_message_count(self, guild_id: int, user_id: int) -> int:
        async with self.user_message_counters_lock:
            return self.user_message_counters.get((guild_id, user_id), 0)

    async def get_pending_guild_message_counts(self, guild_id: int) -> dict[int, int]:
        async with self.user_message_counters_lock:
            return {
                user_id: count
                for (counter_guild_id, user_id), count in self.user_message_counters.items()
                if counter_guild_id == guild_id
            }

    async def flush_user_message_stats(self):
        async with self.user_message_counters_lock:
            counters = dict(self.user_message_counters)
            self.user_message_counters.clear()

        if not counters:
            return

        try:
            await asyncio.to_thread(self.db.bulk_increment_user_message_counts, counters)
        except Exception as e:
            async with self.user_message_counters_lock:
                for key, count in counters.items():
                    self.user_message_counters[key] += count
            self.logger.exception(f"Ошибка сохранения пользовательской статистики сообщений: {e}")

    async def _flush_user_stats_loop(self):
        while not self.is_closed():
            await asyncio.sleep(self.USER_STATS_FLUSH_INTERVAL_SECONDS)
            await self.flush_user_message_stats()

    def _initialize_active_voice_sessions(self):
        for guild in self.guilds:
            self.db.reset_open_voice_sessions(guild.id)
            for channel in guild.voice_channels:
                for member in channel.members:
                    if not member.bot:
                        self.db.start_user_voice_session(
                            guild_id=guild.id,
                            user_id=member.id,
                            channel_id=channel.id,
                        )

    async def _disconnect_bot_from_empty_voice_channel(self, channel):
        if channel is None:
            return

        voice_client = channel.guild.voice_client
        if not voice_client or not voice_client.channel:
            return
        if voice_client.channel.id != channel.id:
            return
        if any(not member.bot for member in channel.members):
            return

        music_cog = self.get_cog("MusicCommands")
        if music_cog and hasattr(music_cog, "disconnect_because_channel_empty"):
            await music_cog.disconnect_because_channel_empty(channel.guild, voice_client)
            return

        await voice_client.disconnect(force=True)
        self.logger.info(
            "Музыка: авто-отключение, в канале не осталось слушателей | guild=%s channel=%s",
            channel.guild.id,
            channel.id,
        )

    async def on_voice_state_update(self, member, before, after):
        if member.bot or not member.guild:
            return

        before_channel = before.channel
        after_channel = after.channel
        if before_channel == after_channel:
            return

        try:
            if before_channel is None and after_channel is not None:
                self.db.start_user_voice_session(
                    guild_id=member.guild.id,
                    user_id=member.id,
                    channel_id=after_channel.id,
                )
                return

            if before_channel is not None and after_channel is None:
                self.db.finish_user_voice_session(
                    guild_id=member.guild.id,
                    user_id=member.id,
                )
                await self._disconnect_bot_from_empty_voice_channel(before_channel)
                return

            if before_channel is not None and after_channel is not None:
                self.db.start_user_voice_session(
                    guild_id=member.guild.id,
                    user_id=member.id,
                    channel_id=after_channel.id,
                )
                await self._disconnect_bot_from_empty_voice_channel(before_channel)
        except Exception as e:
            self.logger.exception(f"Ошибка в on_voice_state_update: {e}")

    async def on_slash_command(self, inter):
        self.log_user_action(
            "Слеш-команда",
            inter,
            f"команда: /{_interaction_name(inter)} | {_format_interaction_options(inter)}",
        )

    async def on_message_command(self, inter):
        data = getattr(inter, "data", None)
        self.log_user_action(
            "Контекстное меню сообщения",
            inter,
            f"команда: {_interaction_name(inter)} | цель: {getattr(data, 'target_id', 'неизвестно')}",
        )

    async def on_user_command(self, inter):
        data = getattr(inter, "data", None)
        self.log_user_action(
            "Контекстное меню пользователя",
            inter,
            f"команда: {_interaction_name(inter)} | цель: {getattr(data, 'target_id', 'неизвестно')}",
        )

    async def on_button_click(self, inter):
        component = getattr(inter, "component", None)
        self.log_user_action(
            "Нажатие кнопки",
            inter,
            f"custom_id: {getattr(component, 'custom_id', 'неизвестно')}",
        )

    async def on_dropdown(self, inter):
        component = getattr(inter, "component", None)
        values = ", ".join(str(value) for value in getattr(inter, "values", []))
        self.log_user_action(
            "Выбор в меню",
            inter,
            f"custom_id: {getattr(component, 'custom_id', 'неизвестно')} | значения: {_short_text(values)}",
        )

    async def on_modal_submit(self, inter):
        values = getattr(inter, "text_values", {})
        filled_fields = ", ".join(values.keys()) if values else "нет"
        self.log_user_action(
            "Отправка формы",
            inter,
            f"форма: {_interaction_name(inter)} | заполненные поля: {filled_fields}",
        )

    async def on_error(self, event_method, *args, **kwargs):
        self.logger.exception(f"Ошибка в событии Discord: {event_method}")

    async def on_slash_command_error(
        self,
        inter: ApplicationCommandInteraction,
        error: Exception
    ) -> None:
        """Обработчик ошибок для слеш-команд"""
        if isinstance(error, commands.MissingPermissions):
            missing_perms = ", ".join(error.missing_permissions)
            self.logger.warning(
                f"Недостаточно прав для команды /{_interaction_name(inter)}: "
                f"{_format_user(inter.author)} | требуется: {missing_perms}"
            )
            await send_interaction_message(
                inter,
                f"Недостаточно прав! Требуются: {missing_perms}",
                ephemeral=True
            )
            return

        self.logger.exception(
            f"Ошибка слеш-команды /{_interaction_name(inter)}: "
            f"{_format_user(inter.author)} | {_format_guild(inter.guild)} | {_format_channel(inter.channel)}",
            exc_info=(type(error), error, error.__traceback__),
        )
        await super().on_slash_command_error(inter, error)

async def load_cogs(bot):
    cogs_dir = Path("./app/modules/cogs")
    for file in cogs_dir.glob("**/*.py"):
        if file.name.endswith(".py") and not file.name.startswith("_"):
            module_path = ".".join(file.with_suffix("").parts)
            try:
                cog = importlib.import_module(module_path)
                if hasattr(cog, "setup"):
                    cog.setup(bot, logger)
            except Exception as e:
                bot.logger.exception(f"Ошибка загрузки кога {file}: {e}")

async def main():    
    pybot = Bot(logger)
    
    @pybot.event
    async def on_message(message):
        if message.author.bot:
            return

        if pybot.is_mi_user(message.author):
            if message.content.startswith("e!"):
                pybot.logger.info(
                    "Prefix-команда | "
                    f"{_format_user(message.author)} | "
                    f"{_format_guild(message.guild)} | "
                    f"{_format_channel(message.channel)} | "
                    f"сообщение ID: {message.id} | "
                    f"команда: {_short_text(message.content)}"
                )
            await pybot.process_commands(message)

        if message.guild is None:
            return

        msg_handler = Messages(logger, pybot, message)
        await msg_handler.process_message()

    await load_cogs(pybot)
    await pybot.start(MAIN_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
