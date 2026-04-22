from disnake.ext import commands
from app.modules.scripts import Scripts

class ContextMenu(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.sc = Scripts(logger, bot)

    @commands.message_command(name="Convert Video")
    async def say_hello(self, inter):
        try:            
            message_id = inter.data.target_id
            await inter.response.defer(ephemeral=False) 
            # Получаем объект сообщения по его ID
            message = await inter.channel.fetch_message(int(message_id))

            # Проверяем, что сообщение содержит вложения
            if message.attachments:
                await self.sc.process_video_conversion(inter, message.attachments)
            else:
                await inter.channel.send("В этом сообщении нет вложений.")
            
        except Exception as e:
            await inter.channel.send("Я не вижу этого сообщения")
            await inter.delete_original_response()
            self.logger.error(f'Ошибка в commands/convert: {e}')
            print(f'Ошибка в commands/convert: {e}')

def setup(bot, logger):
    bot.add_cog(ContextMenu(bot, logger))
