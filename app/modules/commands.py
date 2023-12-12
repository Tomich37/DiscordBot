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
        name="getrole",
        description="Назначить роль",
    )
    @commands.has_permissions(administrator=True, manage_roles=True)
    async def getrole(self, inter, member: disnake.Member, role: disnake.Role):
        self.logger.info(f"Попытка назначения {role.name} участнику {member.display_name}.")
        try:
            await member.add_roles(role)
            await inter.response.send_message(f"Роль {role.name} успешно добавлена участнику {member.display_name}.")
            self.logger.info(f"Роль {role.name} успешно добавлена участнику {member.display_name}.")
        except disnake.errors.Forbidden:
            await inter.response.send_message("У меня нет прав для изменения ролей.")
            self.logger.info(f"Ошибка: недостаточно прав")
        except disnake.errors.HTTPException as e:
            await inter.response.send_message(f"Произошла ошибка")
            self.logger.info(f"Произошла ошибка: {e}")

    @commands.slash_command(
        name="contest",
        description="Организация конкурса",
    )
    @commands.has_permissions(administrator=True)  # Можно изменить на более подходящие права
    async def addreaction(self, inter, channel: disnake.TextChannel, emoji: disnake.Emoji):
        guild_id = inter.guild.id
        channel_id = channel.id
        emoji_str = str(emoji)
        
        print(guild_id, channel_id, emoji_str)
        await inter.response.send_message(f'{guild_id}, {channel_id}, {emoji_str}')

def setup(bot, logger):
    bot.add_cog(SlashCommands(bot, logger))
