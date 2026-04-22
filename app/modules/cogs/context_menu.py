from disnake.ext import commands

from app.modules.scripts import Scripts


class ContextMenu(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.sc = Scripts(logger, bot)

    @commands.message_command(name="Convert Video")
    async def convert_video(self, inter):
        try:
            message_id = inter.data.target_id
            await inter.response.defer(ephemeral=False)
            message = await inter.channel.fetch_message(int(message_id))

            if message.attachments:
                await self.sc.process_video_conversion(inter, message.attachments)
            else:
                await inter.channel.send("В этом сообщении нет вложений.")
        except Exception as e:
            await inter.channel.send("Я не вижу этого сообщения")
            await inter.delete_original_response()
            self.logger.error(f"Ошибка в commands/convert: {e}")
            print(f"Ошибка в commands/convert: {e}")

    @commands.message_command(name="Convert Video to GIF")
    async def convert_video_to_gif(self, inter):
        try:
            message_id = inter.data.target_id
            await inter.response.defer(ephemeral=False)
            message = await inter.channel.fetch_message(int(message_id))

            if message.attachments:
                await self.sc.process_video_conversion(
                    inter,
                    message.attachments,
                    output_format="gif",
                )
            else:
                await inter.channel.send("В этом сообщении нет вложений.")
        except Exception as e:
            await inter.channel.send("Я не вижу этого сообщения")
            await inter.delete_original_response()
            self.logger.error(f"Ошибка в commands/convert_to_gif: {e}")
            print(f"Ошибка в commands/convert_to_gif: {e}")


def setup(bot, logger):
    bot.add_cog(ContextMenu(bot, logger))
