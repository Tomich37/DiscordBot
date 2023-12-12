import disnake
from disnake.ext import commands

class SlashCommands(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger

    @commands.slash_command(
        name="ping",
        description="Возвращает задержку бота",
    )
    async def ping(self, inter):
        await inter.response.send_message("Понг!")

    @commands.slash_command(
        name="help",
        description="Список команд, информация о боте",
    )
    async def help(self, inter):
        await inter.response.send_message("Вот весь список моих команд")

def setup(bot, logger):
    bot.add_cog(SlashCommands(bot, logger))
