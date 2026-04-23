import asyncio
import os
import importlib
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import disnake
from disnake.ext import commands
from disnake import ApplicationCommandInteraction

from app.modules.logger import SetLogs
from app.modules.messages import Messages
from app.modules.scripts import Scripts

load_dotenv()
TEST_TOKEN = os.getenv('DISCORD_TEST_TOKEN')
MAIN_TOKEN = os.getenv('DISCORD_MAIN_TOKEN')
logger = SetLogs().logger


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


class Bot(commands.Bot):
    def __init__(self, logger):
        super().__init__(
            command_prefix=commands.when_mentioned_or("e!"),
            intents=disnake.Intents().all(),
            case_insensitive=True,
            command_sync_flags=commands.CommandSyncFlags.default()
        )
        self.logger = logger
        self.scripts = Scripts(logger, self)
        self.scheduler = AsyncIOScheduler()

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
        print(f"Logged in as {self.user}")
        print("------")
        self.logger.debug(f"Бот запущен как {self.user} (ID: {self.user.id})")

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

    async def on_message_edit(self, before, after):
        if after.author.bot:
            return
        self.logger.info(
            "Изменение сообщения | "
            f"{_format_user(after.author)} | "
            f"{_format_guild(after.guild)} | "
            f"{_format_channel(after.channel)} | "
            f"сообщение ID: {after.id} | "
            f"было: {_short_text(before.content)} | "
            f"стало: {_short_text(after.content)}"
        )

    async def on_message_delete(self, message):
        if message.author.bot:
            return
        self.logger.info(
            "Удаление сообщения | "
            f"{_format_user(message.author)} | "
            f"{_format_guild(message.guild)} | "
            f"{_format_channel(message.channel)} | "
            f"сообщение ID: {message.id} | "
            f"текст: {_short_text(message.content)}"
        )

    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.user.id:
            return
        self.logger.info(
            "Добавление реакции | "
            f"пользователь ID: {payload.user_id} | "
            f"сервер ID: {payload.guild_id} | "
            f"канал ID: {payload.channel_id} | "
            f"сообщение ID: {payload.message_id} | "
            f"реакция: {payload.emoji}"
        )

    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.user.id:
            return
        self.logger.info(
            "Удаление реакции | "
            f"пользователь ID: {payload.user_id} | "
            f"сервер ID: {payload.guild_id} | "
            f"канал ID: {payload.channel_id} | "
            f"сообщение ID: {payload.message_id} | "
            f"реакция: {payload.emoji}"
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
            await inter.response.send_message(
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
        pybot.logger.info(
            "Сообщение пользователя | "
            f"{_format_user(message.author)} | "
            f"{_format_guild(message.guild)} | "
            f"{_format_channel(message.channel)} | "
            f"сообщение ID: {message.id} | "
            f"вложений: {len(message.attachments)} | "
            f"текст: {_short_text(message.content)}"
        )
        await pybot.process_commands(message)
        msg_handler = Messages(logger, pybot, message)
        await msg_handler.process_message()

    await load_cogs(pybot)
    await pybot.start(MAIN_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
