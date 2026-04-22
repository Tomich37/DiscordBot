import disnake
from disnake.ext import commands


class Help(commands.Cog):
    def __init__(self, bot, logger) -> None:
        self.bot = bot
        self.logger = logger

    @commands.slash_command(
        name="help",
        description="Помощь по боту",
    )
    async def help(
        self,
        inter: disnake.GuildCommandInteraction,
    ):
        """
        Помощь по боту.
        """
        embed = disnake.Embed(
            title="Помощь по командам бота",
            description="",
            color=0x00FF00,
        )
        embed.set_author(
            name="Emiliabot",
            url="https://discord.com/api/oauth2/authorize?client_id=602393416017379328&permissions=8&scope=bot+applications.commands",
            icon_url="https://media.discordapp.net/attachments/1186903406196047954/1186903657904623637/avatar_2.png?ex=6594f12b&is=65827c2b&hm=13871565a6497e34268d14785a349ba68e87c2083dc5c2ee3dbdd21a65430a36&=&format=webp&quality=lossless",
        )
        embed.add_field(
            name="Модерация",
            value="""**contest** - организация конкурса в определённом канале
**role** - назначить / снять роль с участника
**add_anonimus_channel** - включить/выключить анонимные сообщения в канале""",
            inline=False,
        )
        embed.add_field(
            name="Другое",
            value="""**help_command** - подробное описание команд
**ping** - пинг бота
**convert** - конвертация видео
**anonimuska** - отправить сообщение от лица бота""",
            inline=False,
        )
        embed.set_footer(text="Made by the_usual_god")
        await inter.response.send_message(embed=embed)

    helpCommand = commands.option_enum(
        {
            "contest": "contest",
            "role": "role",
            "ping": "ping",
            "convert": "convert",
            "add_anonimus_channel": "add_anonimus_channel",
            "anonimuska": "anonimuska",
        }
    )

    @commands.slash_command(
        name="help_command",
        description="Помощь по отдельным командам бота",
    )
    async def help_command(
        self,
        inter: disnake.ApplicationCommandInteraction,
        command: helpCommand,
    ):
        """
        Помощь по отдельным командам.

        Parameters
        ----------
        command: Интересующая команда
        """
        try:
            embed = disnake.Embed(
                title=f"{command}",
                description="",
                color=0x00FF00,
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
                        value="При помощи данной команды можно запустить конкурс в определённом канале.",
                        inline=False,
                    )
                    embed.add_field(
                        name="Параметры",
                        value="""**channel**: Канал, в котором проводится конкурс
**contest_name**: Имя конкретного запуска конкурса. По нему посты привязываются к этому запуску
**emoji**: Эмодзи, которая будет автоматически ставиться на новые сообщения и по которой считаются голоса
**status**: Запуск или завершение конкурса

При завершении выводятся результаты только по тем постам, которые были опубликованы во время этого запуска конкурса.""",
                        inline=False,
                    )
                case "role":
                    embed.add_field(
                        name="Общее описание",
                        value="Назначение или снятие роли с участника сервера.",
                        inline=False,
                    )
                    embed.add_field(
                        name="Параметры",
                        value="""**member**: Участник сервера
**role**: Роль для назначения или снятия
**action**: Назначить или снять роль""",
                        inline=False,
                    )
                case "ping":
                    embed.add_field(
                        name="Общее описание",
                        value="Возвращает задержку ответа от бота.",
                        inline=False,
                    )
                case "convert":
                    embed.add_field(
                        name="Общее описание",
                        value="Конвертация видео во вложениях сообщения.",
                        inline=False,
                    )
                    embed.add_field(
                        name="Параметры",
                        value="**message_id**: ID сообщения с вложением для конвертации",
                        inline=False,
                    )
                case "add_anonimus_channel":
                    embed.add_field(
                        name="Общее описание",
                        value="Разрешает или запрещает анонимные сообщения в выбранном канале.",
                        inline=False,
                    )
                    embed.add_field(
                        name="Параметры",
                        value="""**channel**: Выбор канала
**action**: Включить или отключить возможность отправки сообщений""",
                        inline=False,
                    )
                case "anonimuska":
                    embed.add_field(
                        name="Общее описание",
                        value="Отправляет анонимное сообщение в текущий канал.",
                        inline=False,
                    )
                    embed.add_field(
                        name="Параметры",
                        value="**message**: Сообщение, которое будет отправлено в канал",
                        inline=False,
                    )

            embed.set_footer(text="Made by the_usual_god")
            await inter.response.send_message(embed=embed)
        except Exception as e:
            self.logger.error(f"Ошибка в help_commands/help_command: {e}")
            print(f"Ошибка в help_commands/help_command: {e}")


def setup(bot, logger):
    bot.add_cog(Help(bot, logger))
