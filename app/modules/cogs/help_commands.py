import disnake
from disnake.ext import commands

class Help(commands.Cog):
    def __init__(self, bot, logger) -> None:
        self.bot = bot
        self.logger = logger

    @commands.slash_command(
            name='help',
            description='Помощь по боту'
        )
    async def help(
        self,
        inter: disnake.GuildCommandInteraction,
    ):
        """
            Помощь по боту
        """
        embed = disnake.Embed(
            title=f"Помощь по командам бота",
            description="",
            color=0x00ff00
        )
        embed.add_field(
            name="Модерация",
            value="""**contest** - организация конкурса в поределенном канале
            **role** - назначить / снять роль с участника""",
            inline=False
        )
        embed.add_field(
            name="Другое",
            value="""**ping** - пинг бота""",
            inline=False
        )
        embed.set_footer(text=f'Made by the_usual_god')
        await inter.response.send_message(embed=embed)

def setup(bot, logger):
    bot.add_cog(Help(bot, logger))