import disnake
from disnake.ext import commands
from app.modules.database import Database
from app.modules.scripts import Scripts

class SlashCommands(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db= Database()
        self.sc = Scripts(logger, bot)

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
    ):
        """
            Конвертация видео в рабочее

            Parameters
            ----------
            message_id: id на сообщение, видео которого надо сконвертировать
        """
        try:
            await inter.response.defer(ephemeral=False) 
            # Получаем объект сообщения по его ID
            message = await inter.channel.fetch_message(int(message_id))

            # Проверяем, что сообщение содержит вложения
            if message.attachments:
                for attachment in message.attachments:
                    save_path = "./app/modules/temp/"
                    await attachment.save(f"{save_path}downloaded_{attachment.filename}")
                await self.sc.video_convert()
                await self.sc.send_files(inter, message_id)
            else:
                await inter.channel.send("В этом сообщении нет вложений.")     

            # Удаление уведомления о том что бот думает
            await inter.delete_original_response()
            
        except Exception as e:
            await inter.channel.send("Я не вижу этого сообщения")  
            await inter.delete_original_response()
            self.logger.error(f'Ошибка в commands/convert: {e}')
            print(f'Ошибка в commands/convert: {e}')

def setup(bot, logger):
    bot.add_cog(SlashCommands(bot, logger))
