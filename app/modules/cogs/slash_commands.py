import disnake
import disnake.ext
from disnake.ext import commands
from app.modules.database import Database
from app.modules.scripts import Scripts
from app.modules.voice import VoiceScripts

class SlashCommands(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db= Database()
        self.sc = Scripts(logger, bot)
        self.voice_scripts = VoiceScripts(logger, bot)

    @commands.slash_command(
        name="ping",
        description="Понг",
    )
    async def ping(self, inter):
        await inter.response.send_message(f"Понг! {round(self.bot.latency * 1000)}мс")

    @commands.slash_command(
        name="connect",
        description="Connect the bot to your current voice channel.",
    )
    async def connect(self, inter: disnake.GuildCommandInteraction):
        await inter.response.defer(ephemeral=True)
        await self.voice_scripts.connect_to_requester_channel(inter)

    @commands.slash_command(
        name="disconnect",
        description="Disconnect the bot if you share its current voice channel.",
    )
    async def disconnect(self, inter: disnake.GuildCommandInteraction):
        await inter.response.defer(ephemeral=True)
        await self.voice_scripts.disconnect_with_requester(inter)

    roleMenegment = commands.option_enum({"Назначить роль": "add", "Снять роль": "take"})  
    @commands.slash_command(
        name="role",
        description="Назначить/снять роль",
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
            Назначение роли участнику сервера

            Parameters
            ----------
            member: Выберите пользователя для назначения роли
            role: Выберите роль для назначения на пользователя
            action: Назначить или снять роль
        """
        try:
            if action == 'add':
                await member.add_roles(role)
                await inter.response.send_message(f"Роль {role.name} успешно добавлена участнику {member.display_name}.")
                self.logger.info(f"Роль {role.name} успешно добавлена участнику {member.display_name}.")
            else:
                await member.remove_roles(role)
                await inter.response.send_message(f"Роль {role.name} успешно снята с участника {member.display_name}.")
                self.logger.info(f"Снятие роли {role.name} с участника {member.display_name}.")
        except disnake.errors.Forbidden:
            await inter.response.send_message("У меня нет прав для изменения ролей.")
            self.logger.info(f"Ошибка: недостаточно прав")
        except Exception as e:
            await inter.response.send_message(f"Произошла ошибка")
            self.logger.info(f"Произошла ошибка: {e}")

    contestStatus = commands.option_enum({"Запуск конкурса": "start", "Завершение конкурса": "stop"})
    @commands.slash_command(
        name="contest",
        description="Организация конкурса",
    )
    @commands.has_permissions(administrator=True)
    async def contest(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: disnake.TextChannel,
        emoji: disnake.Emoji,
        status: contestStatus,        
    ):
        """
            Создание и завершение конкурса

            Parameters
            ----------
            channel: Выбор канала, в котором будет проводться или завершаться конкурс
            emoji: Эмодзи, которая будет автоматически проставляться на новых сообщениях
            status: Параметр, управляющий стартом и завершением конкурса
        """
        try:
            await inter.response.defer(ephemeral=False) # Чтоб бот не выдавал ошибку из-за зависания
            guild_id = inter.guild.id
            channel_id = channel.id
            emoji_str = str(emoji)
            status = True if status == 'start' else False
            self.db.create_update_contest(guild_id, channel_id, emoji_str, bool(status))
            
            if status:
                await inter.send(f'Конкурс в канале <#{channel_id}> активирован. Выбранное емодзи: {emoji_str}', ephemeral=False)
            else:
                await self.sc.read_messages_with_reaction(channel_id, emoji_str, inter)
                await inter.send(f'Конкурс в канале <#{channel_id}> завершен', ephemeral=False)
        except Exception as e:
            self.logger.error(f'Ошибка в commands/contest: {e}')
            print(f'Ошибка в commands/contest: {e}')

    @commands.slash_command(
        name="convert",
        description="Конвертация видео",
    )
    async def convert(
        self,
        inter,
        message_id: str,
        channel: disnake.TextChannel = None
    ):
        """
            Конвертация видео в рабочее

            Parameters
            ----------
            message_id: id на сообщение, видео которого надо сконвертировать
            channel: канал, где находится сообщение (если не указан, ищет в текущем)
        """
        try:
            await inter.response.defer(ephemeral=False) 
            
            # Определяем канал для поиска
            target_channel = channel if channel else inter.channel
            
            # Получаем объект сообщения по его ID
            message = await target_channel.fetch_message(int(message_id))

            # Проверяем, что сообщение содержит вложения
            if message.attachments:
                save_path = "./app/modules/temp/"
                for attachment in message.attachments:
                    await attachment.save(f"{save_path}downloaded_{attachment.filename}")
                await self.sc.video_convert()
                await self.sc.send_files(inter)
            else:
                await inter.followup.send("В этом сообщении нет вложений.")     
        except disnake.NotFound:
            await inter.followup.send("Сообщение не найдено. Убедитесь, что вы указали правильный ID и канал.")
            await inter.delete_original_response()
        except Exception as e:
            await inter.followup.send(f"Произошла ошибка: {str(e)}")
            await inter.delete_original_response()
            self.logger.error(f'Ошибка в commands/convert: {e}')
            print(f'Ошибка в commands/convert: {e}')

    statisticStatus = commands.option_enum({"Запуск сбора статистики": "start", "Завершение сбора статистики": "stop"})
    @commands.slash_command(
        name="add_statistic",
        description="Статистика канала",
    )
    @commands.has_permissions(administrator=True, manage_roles=True)
    async def add_statistic(
        self,
        inter,
        channel: disnake.TextChannel,
        status: statisticStatus,  
    ):
        """
            Сбор статистики активности по определенному каналу

            Parameters
            ----------
            channel_id: id на канал, который будет отслеживаться
            status: Параметр, управляющий стартом и завершением отслеживания канала
        """
        try:       
            guild_id = inter.guild.id   
            channel_id = channel.id
            status = True if status == 'start' else False

            self.db.create_update_channel_statistic(guild_id, channel_id, bool(status))

            if status:
                await inter.send(f'Отслеживание статистики в канале <#{channel_id}> активировано.', ephemeral=False)
            else:
                await inter.send(f'Отслеживание статистики в канале <#{channel_id}> завершено', ephemeral=False)
            
        except Exception as e:
            await inter.channel.send(f'Ошибка в commands/slash_command/add_statistic: {e}')
            self.logger.error(f'Ошибка в commands/slash_command/add_statistic: {e}')
            print(f'Ошибка в commands/slash_command/add_statistic: {e}')

    channelAnonimusMenegment = commands.option_enum({"Добавить канал": "add", "Удалить канал": "del"})  
    @commands.slash_command(
        name="add_anonimus_channel",
        description="Добавить/удалить канал из списка разрешенных для анонимных сообщений",
    )
    @commands.has_permissions(administrator=True)
    async def add_anonimus_channel(
        self, 
        inter: disnake.GuildCommandInteraction,
        channel: disnake.TextChannel,     
        action: channelAnonimusMenegment,
    ):
        """
            Назначение роли участнику сервера

            Parameters
            ----------
            channel: Выберите канал для редактирования прав
            action: Выдать или забрать право на публикацию анонимных сообщений
        """
        try:       
            guild_id = inter.guild.id   
            channel_id = channel.id
            action = True if action == 'add' else False

            self.db.create_update_channel_anonimus(guild_id, channel_id, bool(action))

            if action:
                await inter.send(f'Анонимные сообщения в канале <#{channel_id}> активированы.', ephemeral=False)
            else:
                await inter.send(f'Анонимные сообщения в канале <#{channel_id}> выключены', ephemeral=False)
            
        except Exception as e:
            await inter.channel.send(f'Ошибка в commands/slash_command/channelAnonimus: {e}')
            self.logger.error(f'Ошибка в commands/slash_command/channelAnonimus: {e}')
            print(f'Ошибка в commands/slash_command/channelAnonimus: {e}')

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
            Отправка анонимного сообщения в этом канале

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
                    ephemeral=True
                )
            
            # Создаём эмбед
            embed = disnake.Embed(
                title="Анонимуська",
                description=message[:4096],
                color=0x00008B
            )
            embed.set_author(
                name="Emiliabot",
                url="https://discord.com/api/oauth2/authorize?client_id=602393416017379328&permissions=8&scope=bot+applications.commands",
                icon_url="https://media.discordapp.net/attachments/1186903406196047954/1186903657904623637/avatar_2.png",
            )
            embed.set_footer(text="Made by the_usual_god")

            # Отправляем эмбед в канал
            await inter.response.defer(ephemeral=True)   
            await inter.channel.send(embed=embed)
            await inter.delete_original_response()

            # Логируем действие
            self.logger.info(
                f"Анонимное сообщение от {inter.author} (ID: {inter.author.id}) "
                f"в канале {inter.channel} (ID: {channel_id}): {message[:100]}"
            )

        except Exception as e:
            error_msg = f"Ошибка при отправке анонимного сообщения: {e}"
            await inter.response.send_message(error_msg, ephemeral=True)  # Уведомляем автора
            self.logger.error(f"Ошибка в commands/slash_command/send_anonimus_channel: {e}")
            print(error_msg)

    # @commands.slash_command(
    #     name="test",
    #     description="Для тестовых команд",
    # )
    # async def test(
    #     self,
    #     inter,
    # ):
    #     """
    #         Для тестирования команд
    #     """
    #     try:
    #         await inter.response.defer(ephemeral=False)
    #         await self.sc.send_daily_statistics()            
    #     except Exception as e:
    #         await inter.channel.send(f'Ошибка в commands/test: {e}')
    #         await inter.delete_original_response()
    #         self.logger.error(f'Ошибка в commands/test: {e}')
    #         print(f'Ошибка в commands/test: {e}')




def setup(bot, logger):
    bot.add_cog(SlashCommands(bot, logger))
