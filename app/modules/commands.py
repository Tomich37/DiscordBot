import disnake
from disnake.ext import commands

class SlashCommands:
    def __init__(self, logger, bot):
        self.logger = logger
        self.bot = bot

    @commands.slash_command(
        name="ping",
        description="Возвращает задержку бота",
    )
    async def ping(self, inter):
        await inter.response.send_message("Понг!")
