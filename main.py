from app.modules.logger import SetLogs
from app.modules.messages import Messages
from app.modules.commands import setup as setup_commands
import configparser
import disnake
from disnake.ext import commands

# токен
config = configparser.ConfigParser()
config.read('./config.ini')
token = config.get('token', 'token')
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

# Обработка слэш-команд
setup_commands(pybot, logger)

pybot.run(token)
