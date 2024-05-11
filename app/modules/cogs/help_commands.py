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
        embed.set_author(
            name="Emiliabot",
            url="https://discord.com/api/oauth2/authorize?client_id=602393416017379328&permissions=8&scope=bot+applications.commands",
            icon_url="https://media.discordapp.net/attachments/1186903406196047954/1186903657904623637/avatar_2.png?ex=6594f12b&is=65827c2b&hm=13871565a6497e34268d14785a349ba68e87c2083dc5c2ee3dbdd21a65430a36&=&format=webp&quality=lossless",
        )        
        embed.add_field(
            name="Модерация",
            value="""**contest** - организация конкурса в определенном канале
**role** - назначить / снять роль с участника""",
            inline=False
        )
        embed.add_field(
            name="Другое",
            value="""**help_command** - подробное описание команд
**ping** - пинг бота
**convert** - конвертация видео в рабочее""",
            inline=False
        )
        embed.set_footer(text=f'Made by the_usual_god')
        await inter.response.send_message(embed=embed)

    helpCommand = commands.option_enum({"contest": "contest", "role": "role", "ping": "ping", "convert": "convert"})
    @commands.slash_command(
            name='help_command',
            description='Помощь по отдельным командам бота'
        )
    async def help_command(
        self,
        inter: disnake.ApplicationCommandInteraction,
        command: helpCommand,
    ):
        """
            Помощь по отдельным командам

            Parameters
            ----------
            command: Интересующая команда
        """
        try:
            embed = disnake.Embed(
                title=f"{command}",
                description="",
                color=0x00ff00
            )
            embed.set_author(
                name="Emiliabot",
                url="https://discord.com/api/oauth2/authorize?client_id=602393416017379328&permissions=8&scope=bot+applications.commands",
                icon_url="https://media.discordapp.net/attachments/1186903406196047954/1186903657904623637/avatar_2.png?ex=6594f12b&is=65827c2b&hm=13871565a6497e34268d14785a349ba68e87c2083dc5c2ee3dbdd21a65430a36&=&format=webp&quality=lossless",
            )
            match command:
                case "contest":
                    embed.add_field(
                        name="Общее описание",
                        value="""При помощи данной команды можно запустить конкурс в определенном канале""",
                        inline=False
                    )
                    embed.add_field(
                        name="Параметры",
                        value="""**channel**: Выбор канала, в котором будет проводться или завершаться конкурс                                
**emoji**: Эмодзи, которая будет автоматически проставляться на новых сообщениях. 
Дополнительно по указанному емодзи просчитываются голоса (чем больше реакций - тем выше место). 
По какой эмодззи конкурс начался, по той и завершается, возможно несколько конкурсов в одном канале по разным емодзи                                
**status**: Параметр, управляющий стартом и завершением конкурса. 
При выборе завершения конкурса, автоматически будут выведены результаты (первые 10 мест) в канал, в котором проводился конкурс""",
                        inline=False
                    )
                case "role":
                    embed.add_field(
                        name="Общее описание",
                        value="""При помощи данной команды можно назначить или снять роль с участника сервера""",
                        inline=False
                    )
                    embed.add_field(
                        name="Параметры",
                        value="""**member**: Выбор участника сервера
**role**: Выбор роли для назначения/снятия (роль должна не принадлежать другому боту и находиться ниже роли Эмилии в списке ролей)
**action**: Выбор из параметра назначить или снять роль""",
                        inline=False
                    )
                case "ping":
                    embed.add_field(
                        name="Общее описание",
                        value="""Возвращение задержки ответа на выполнение команды от бота""",
                        inline=False
                    )
                case "convert":
                    embed.add_field(
                        name="Общее описание",
                        value="""При помощи данной команды идет конвертация видео в рабочее""",
                        inline=False
                    )
                    embed.add_field(
                        name="Параметры",
                        value="""**message_id**: Id сообщения с вложением, которое необходимо конвертировать""",
                        inline=False
                    )
            embed.set_footer(text=f'Made by the_usual_god')
            await inter.response.send_message(embed=embed)
        except Exception as e:
            self.logger.error(f'Ошибка в help_commands/help_command: {e}')
            print(f'Ошибка в help_commands/help_command: {e}')
            


def setup(bot, logger):
    bot.add_cog(Help(bot, logger))