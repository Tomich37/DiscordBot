from disnake.ext import commands
from app.modules.scripts import Scripts

class ContextMenu(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.sc = Scripts(logger, bot)

    @commands.message_command(name="Convert Video")
    async def say_hello(self, inter):
        message_id = inter.data.target_id
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
    bot.add_cog(ContextMenu(bot, logger))