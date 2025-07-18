import asyncio
from app.modules.logger import SetLogs
from app.modules.messages import Messages
from app.modules.scripts import Scripts

import disnake
import os
import importlib
from disnake.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from dotenv import load_dotenv

# токен
load_dotenv()
TEST_TOKEN = os.getenv('DISCORD_TEST_TOKEN')
MAIN_TOKEN = os.getenv('DISCORD_MAIN_TOKEN')
logger = SetLogs().logger

class Bot(commands.Bot):
    def __init__(self, logger):
        super().__init__(command_prefix=commands.when_mentioned_or("e!"), intents=disnake.Intents().all(),
                         case_insensitive=True, command_sync_flags=commands.CommandSyncFlags.default())
        self.logger = logger

        self.scripts = Scripts(logger, self)  # Инициализация скрипта
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(
            self.scripts.send_daily_statistics, 
            'cron', 
            hour=0, 
            minute=0,
            misfire_grace_time=60  # Задаем время в секундах, в течение которого задача все еще может быть выполнена, если пропущена
        )
        self.scheduler.start()

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        print("------")

async def main():
    pybot = Bot(logger)
    
    # Обработка сообщений из чата
    @pybot.event
    async def on_message(message):
        msg_handler = Messages(logger, pybot, message)
        await msg_handler.process_message()

    cogs_dir = "./app/modules/cogs"
    # Обработка слэш-команд
    for file in os.listdir(cogs_dir):
        if file.endswith(".py"):
            module_name = f"app.modules.cogs.{file[:-3]}"
            cog = importlib.import_module(module_name)
            cog.setup(pybot, logger)

    await pybot.start(TEST_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())