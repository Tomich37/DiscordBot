from app.modules.logger import SetLogs
from app.modules.messages import Messages

import configparser
import disnake
import os
import importlib
from disnake.ext import commands

# токен
config = configparser.ConfigParser()
config.read('./config.ini')
token = config.get('token', 'test_token')
logger = SetLogs().logger

class Bot(commands.Bot):
    def __init__(self, logger):
        super().__init__(command_prefix=commands.when_mentioned_or("e!"), intents=disnake.Intents().all(),
                         case_insensitive=True, command_sync_flags=commands.CommandSyncFlags.default())
        self.logger = logger

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        print("------")
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

pybot.run(token)
