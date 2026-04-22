import disnake
from disnake.ext import commands

from app.modules.database import Database
from app.modules.scripts import Scripts


class SlashCommands(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db = Database()
        self.sc = Scripts(logger, bot)

    convert_formats = commands.option_enum({"MOV": "mov", "GIF (до 10 сек)": "gif"})

    @commands.slash_command(
        name="ping",
        description="Понг",
    )
    async def ping(self, inter):
        await inter.response.send_message(f"Понг! {round(self.bot.latency * 1000)}мс")

    roleMenegment = commands.option_enum({"Назначить роль": "add", "Снять роль": "take"})

    @commands.slash_command(
        name="role",
        description="Назначить/снять роль",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True, manage_roles=True),
    )
    @commands.has_permissions(administrator=True, manage_roles=True)
    async def role(
        self,
        inter: disnake.GuildCommandInteraction,
        member: disnake.Member,
        role: disnake.Role,
        action: roleMenegment,
    ):
        """
        Назначение роли участнику сервера.

        Parameters
        ----------
        member: Выберите пользователя для назначения роли
        role: Выберите роль для назначения пользователю
        action: Назначить или снять роль
        """
        try:
            if action == "add":
                await member.add_roles(role)
                await inter.response.send_message(
                    f"Роль {role.name} успешно добавлена участнику {member.display_name}."
                )
                self.logger.info(
                    f"Роль {role.name} успешно добавлена участнику {member.display_name}."
                )
            else:
                await member.remove_roles(role)
                await inter.response.send_message(
                    f"Роль {role.name} успешно снята с участника {member.display_name}."
                )
                self.logger.info(
                    f"Снятие роли {role.name} с участника {member.display_name}."
                )
        except disnake.errors.Forbidden:
            await inter.response.send_message("У меня нет прав для изменения ролей.")
            self.logger.info("Ошибка: недостаточно прав")
        except Exception as e:
            await inter.response.send_message("Произошла ошибка")
            self.logger.info(f"Произошла ошибка: {e}")

    contestStatus = commands.option_enum({"Запуск конкурса": "start", "Завершение конкурса": "stop"})

    @commands.slash_command(
        name="contest",
        description="Организация конкурса",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True),
    )
    @commands.has_permissions(administrator=True)
    async def contest(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: disnake.TextChannel,
        contest_name: str,
        emoji: disnake.Emoji,
        status: contestStatus,
        top_count: commands.Range[int, 1, 50] = 10,
    ):
        """
        Создание и завершение конкурса.

        Parameters
        ----------
        channel: Выбор канала, в котором будет проводиться или завершаться конкурс
        contest_name: Уникальное имя запуска конкурса
        emoji: Эмодзи, которая будет автоматически проставляться на новых сообщениях
        top_count: Сколько лучших мест выводить при завершении конкурса
        status: Параметр, управляющий стартом и завершением конкурса
        """
        try:
            # Даём боту время на обработку без таймаута Discord.
            await inter.response.defer(ephemeral=False)

            guild_id = inter.guild.id
            channel_id = channel.id
            emoji_str = str(emoji)
            is_start = status == "start"

            if is_start:
                contest = self.db.start_contest_run(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                    emoji_str=emoji_str,
                )
                self.db.create_update_contest(guild_id, channel_id, emoji_str, True)
                await inter.send(
                    f"Конкурс `{contest.contest_name}` в канале <#{channel_id}> активирован. "
                    f"Выбранное эмодзи: {emoji_str}",
                    ephemeral=False,
                )
            else:
                contest = self.db.stop_contest_run(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                )
                if not contest:
                    await inter.send(
                        f"Активный конкурс `{contest_name}` в канале <#{channel_id}> не найден.",
                        ephemeral=False,
                    )
                    return

                await self.sc.read_messages_with_reaction(
                    channel_id=channel_id,
                    emoji=contest.emoji_str,
                    inter=inter,
                    contest_id=contest.id,
                    top_count=top_count,
                )
                if not self.db.get_active_contests_for_channel(guild_id, channel_id):
                    self.db.create_update_contest(guild_id, channel_id, contest.emoji_str, False)
                await inter.send(
                    f"Конкурс `{contest.contest_name}` в канале <#{channel_id}> завершён.",
                    ephemeral=False,
                )
        except Exception as e:
            self.logger.error(f"Ошибка в commands/contest: {e}")
            print(f"Ошибка в commands/contest: {e}")

    @commands.slash_command(
        name="convert",
        description="Конвертация видео",
    )
    async def convert(
        self,
        inter,
        message_id: str,
        output_format: convert_formats = "mov",
        channel: disnake.TextChannel = None,
    ):
        """
        Конвертация видео в рабочее.

        Parameters
        ----------
        message_id: id сообщения, видео которого надо сконвертировать
        channel: Канал, где находится сообщение
        """
        try:
            await inter.response.defer(ephemeral=False)
            target_channel = channel if channel else inter.channel
            message = await target_channel.fetch_message(int(message_id))

            if message.attachments:
                await self.sc.process_video_conversion(
                    inter,
                    message.attachments,
                    output_format=output_format,
                )
            else:
                await inter.followup.send("В этом сообщении нет вложений.")
        except disnake.NotFound:
            await inter.followup.send(
                "Сообщение не найдено. Убедитесь, что указан правильный ID и канал."
            )
            await inter.delete_original_response()
        except Exception as e:
            await inter.followup.send(f"Произошла ошибка: {str(e)}")
            await inter.delete_original_response()
            self.logger.error(f"Ошибка в commands/convert: {e}")
            print(f"Ошибка в commands/convert: {e}")

    statisticStatus = commands.option_enum(
        {"Запуск сбора статистики": "start", "Завершение сбора статистики": "stop"}
    )

    @commands.slash_command(
        name="add_statistic",
        description="Статистика канала",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True, manage_roles=True),
    )
    @commands.has_permissions(administrator=True, manage_roles=True)
    async def add_statistic(
        self,
        inter,
        channel: disnake.TextChannel,
        status: statisticStatus,
    ):
        """
        Сбор статистики активности по определённому каналу.

        Parameters
        ----------
        channel: Канал для отслеживания
        status: Параметр, управляющий стартом и завершением отслеживания канала
        """
        try:
            guild_id = inter.guild.id
            channel_id = channel.id
            is_active = status == "start"

            self.db.create_update_channel_statistic(guild_id, channel_id, is_active)

            if is_active:
                await inter.send(
                    f"Отслеживание статистики в канале <#{channel_id}> активировано.",
                    ephemeral=False,
                )
            else:
                await inter.send(
                    f"Отслеживание статистики в канале <#{channel_id}> завершено",
                    ephemeral=False,
                )
        except Exception as e:
            await inter.channel.send(f"Ошибка в commands/slash_command/add_statistic: {e}")
            self.logger.error(f"Ошибка в commands/slash_command/add_statistic: {e}")
            print(f"Ошибка в commands/slash_command/add_statistic: {e}")

    channelAnonimusMenegment = commands.option_enum(
        {"Добавить канал": "add", "Удалить канал": "del"}
    )

    @commands.slash_command(
        name="add_anonimus_channel",
        description="Добавить/удалить канал из списка разрешённых для анонимных сообщений",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True),
    )
    @commands.has_permissions(administrator=True)
    async def add_anonimus_channel(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: disnake.TextChannel,
        action: channelAnonimusMenegment,
    ):
        """
        Управление списком каналов для анонимных сообщений.

        Parameters
        ----------
        channel: Выберите канал для редактирования прав
        action: Выдать или забрать право на публикацию анонимных сообщений
        """
        try:
            guild_id = inter.guild.id
            channel_id = channel.id
            is_active = action == "add"

            self.db.create_update_channel_anonimus(guild_id, channel_id, is_active)

            if is_active:
                await inter.send(
                    f"Анонимные сообщения в канале <#{channel_id}> активированы.",
                    ephemeral=False,
                )
            else:
                await inter.send(
                    f"Анонимные сообщения в канале <#{channel_id}> выключены",
                    ephemeral=False,
                )
        except Exception as e:
            await inter.channel.send(f"Ошибка в commands/slash_command/channelAnonimus: {e}")
            self.logger.error(f"Ошибка в commands/slash_command/channelAnonimus: {e}")
            print(f"Ошибка в commands/slash_command/channelAnonimus: {e}")

    @commands.slash_command(
        name="anonimuska",
        description="Отправить анонимное сообщение в этом канале",
    )
    async def send_anonimus_channel(
        self,
        inter: disnake.GuildCommandInteraction,
        message: str,
    ):
        """
        Отправка анонимного сообщения в этом канале.

        Parameters
        ----------
        message: Введите сообщение
        """
        try:
            channel_id = inter.channel.id
            anonimus_channels = self.db.get_all_anonimus_channel()

            if channel_id not in anonimus_channels:
                return await inter.response.send_message(
                    "Данный канал не поддерживает анонимные сообщения",
                    ephemeral=True,
                )

            embed = disnake.Embed(
                title="Анонимуська",
                description=message[:4096],
                color=0x00008B,
            )
            embed.set_author(
                name="Emiliabot",
                url="https://discord.com/api/oauth2/authorize?client_id=602393416017379328&permissions=8&scope=bot+applications.commands",
                icon_url="https://media.discordapp.net/attachments/1186903406196047954/1186903657904623637/avatar_2.png",
            )
            embed.set_footer(text="Made by the_usual_god")

            await inter.response.defer(ephemeral=True)
            await inter.channel.send(embed=embed)
            await inter.delete_original_response()

            self.logger.info(
                f"Анонимное сообщение от {inter.author} (ID: {inter.author.id}) "
                f"в канале {inter.channel} (ID: {channel_id}): {message[:100]}"
            )
        except Exception as e:
            error_msg = f"Ошибка при отправке анонимного сообщения: {e}"
            await inter.response.send_message(error_msg, ephemeral=True)
            self.logger.error(f"Ошибка в commands/slash_command/send_anonimus_channel: {e}")
            print(error_msg)


def setup(bot, logger):
    bot.add_cog(SlashCommands(bot, logger))
