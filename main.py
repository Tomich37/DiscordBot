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

    async def on_slash_command_error(
        self,
        inter: ApplicationCommandInteraction,
        error: Exception
    ) -> None:
        """Обработчик ошибок для слеш-команд"""
        if isinstance(error, commands.MissingPermissions):
            missing_perms = ", ".join(error.missing_permissions)
            await inter.response.send_message(
                f"Недостаточно прав! Требуются: {missing_perms}",
                ephemeral=True
            )
            return            
        await super().on_slash_command_error(inter, error)

async def load_cogs(bot):
    cogs_dir = Path("./app/modules/cogs")
    for file in cogs_dir.glob("**/*.py"):
        if file.name.endswith(".py") and not file.name.startswith("_"):
            module_path = str(file).replace("/", ".").replace(".py", "")
            try:
                cog = importlib.import_module(module_path)
                if hasattr(cog, "setup"):
                    cog.setup(bot, logger)
            except Exception as e:
                bot.logger.error(f"Ошибка загрузки кога {file}: {e}")

async def main():    
    pybot = Bot(logger)
    
    @pybot.event
    async def on_message(message):
        if message.author.bot:
            return
        await pybot.process_commands(message)
        msg_handler = Messages(logger, pybot, message)
        await msg_handler.process_message()

    await load_cogs(pybot)
    await pybot.start(MAIN_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())