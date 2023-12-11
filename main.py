from app.modules.logger import SetLogs
from app.modules.messages import Messages
from app.modules.commands import SlashCommands
import configparser
import disnake
from disnake.ext import commands

#токен
config = configparser.ConfigParser()
config.read('./config.ini')
token = config.get('token', 'token')
logger = SetLogs().logger

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or("e!"), intents=disnake.Intents().all(),
                         case_insensitive=True, command_sync_flags=commands.CommandSyncFlags.default())
    
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        print("------")
pybot = Bot()

#Обработка собщений из чата
@pybot.event
async def on_message(message):
    msg_handler = Messages(logger, pybot, message)
    await msg_handler.process_message()

#Обработка слэш команд
slash_commands = SlashCommands(logger, pybot)
pybot.add_slash_command(slash_commands.ping)

pybot.run(token)