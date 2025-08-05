import disnake
import matplotlib.pyplot as plt

from io import BytesIO
from PIL import Image
import re, os
from moviepy import VideoFileClip
from datetime import date, timedelta

from app.modules.database import Database

class Scripts:
    def __init__(self, logger, bot) -> None:
        self.logger = logger
        self.bot = bot
        self.db = Database
        self.all_messages = {}

    # Считывание сообщений и сортировка по реакции
    async def read_messages_with_reaction(self, channel_id, emoji, inter):
        try:
            channel = self.bot.get_channel(channel_id)
            match = re.match(r'<a?:(\w+):(\d+)>', emoji)
            if match:
                name = match.group(1)
                emoji_id = int(match.group(2))
            else:
                return None
            
            if not channel:
                self.logger.warning(f"Канал с id {channel_id} не найден.")
                await inter.response.send_message(f'Канал с id {channel_id} не найден.')
                return
            
            target_emoji = disnake.PartialEmoji(name=name, id=emoji_id)
            async for message in channel.history(limit=1000):
                # Получаем список реакций под сообщением
                reactions = message.reactions

                # Проверяем, есть ли нужная реакция в списке
                if any(reaction.emoji == target_emoji for reaction in reactions):
                    reaction = disnake.utils.get(message.reactions, emoji=target_emoji)

                    self.all_messages[message.id] = {
                        "reactions_count": reaction.count,
                        "content": message.content,
                        "attachments": [attachment.url for attachment in message.attachments],
                        "url": message.jump_url
                    }
            sorted_messages = sorted(self.all_messages.values(), key=lambda x: x["reactions_count"], reverse=True)
            await self.send_embeds(sorted_messages, channel)
            
        except Exception as e:
            self.logger.error(f'Ошибка в scripts/read_messages_with_reaction: {e}')
            print(f'Ошибка в scripts/read_messages_with_reaction: {e}')

    # Генерация и отправка эмбедов
    async def send_embeds(self, sorted_messages, channel, top_count=10):
        try:
            place = 0
            for sorted_message in sorted_messages[:top_count]:
                    place += 1
                    embed = disnake.Embed(
                        title=f"{place} место",
                        description=sorted_message["content"],
                        color=0x00ff00
                    )                
                    if sorted_message["attachments"]:
                        # Предполагаем, что первое вложение является изображением или видео
                        embed.set_image(url=sorted_message["attachments"][0])
                    embed.add_field(
                        name="Ссылка на оригинал",
                        value=sorted_message["url"],
                        inline=False
                    )
                    embed.set_footer(text=f'Количество голосов {sorted_message["reactions_count"]}')
                    await channel.send(embed=embed)
            self.all_messages.clear
        except Exception as e:
            self.logger.error(f'Ошибка в scripts/send_embeds: {e}')
            print(f'Ошибка в scripts/send_embeds: {e}')
    
    # Конвертация видео
    async def video_convert(self):
        try:
            # Путь к папке с видеофайлами
            video_folder = "./app/modules/temp"

            # Создаем папку, если она не существует
            os.makedirs(video_folder, exist_ok=True)

            # Получаем список всех файлов в папке
            files = os.listdir(video_folder)

            # Фильтруем только видеофайлы
            video_files = [file for file in files if file.lower().endswith((".mp4", ".avi", ".mkv"))]

            # Конвертируем каждый видеофайл в формат MOV
            for video_file in video_files:
                input_path = os.path.join(video_folder, video_file)
                output_file = os.path.splitext(video_file)[0] + ".mov"
                output_path = os.path.join(video_folder, output_file)
                
                try:
                    # Создаем объект VideoFileClip для текущего видеофайла
                    with VideoFileClip(input_path) as video:
                        # Сохраняем видео в MOV формате
                        video.write_videofile(
                            output_path,
                            codec='libx264',
                            audio_codec='aac'
                        )
                    
                    # Удаление исходников
                    os.remove(input_path)
                    print(f"Успешно конвертировано: {video_file} -> {output_file}")
                    
                except Exception as clip_error:
                    print(f"Ошибка при обработке файла {video_file}: {str(clip_error)}")
                    continue      
        except Exception as e:
            self.logger.error(f'Ошибка в scripts/video_convert: {e}')
            print(f'Ошибка в scripts/video_convert: {e}')

    # Создание и отправка сообщения с вложениями
    async def send_files(self, inter):
        try:
            video_folder = "./app/modules/temp"
            files = os.listdir(video_folder)

            # Создаем список для хранения объектов disnake.File
            mp4_files = []

            # Получаем список всех файлов в указанном каталоге
            for filename in os.listdir(video_folder):
                if filename.lower().endswith(".mov"):
                    file_path = os.path.join(video_folder, filename)
                    mp4_files.append(disnake.File(file_path))
            
            # Отправляем сообщение с вложениями
            await inter.followup.send(
                content=f"{inter.author.mention}, ваши конвертированные видео:",
                files=mp4_files
            )

            # Подчищаем файлы
            for file in files:
                file_path = os.path.join(video_folder, file)
                if os.path.exists(file_path):
                    os.remove(file_path)
        except Exception as e:
            await inter.followup.send(content=f'Ошибка: {e}')

            # Подчищаем файлы
            for file in files:
                file_path = os.path.join(video_folder, file)
                if os.path.exists(file_path):
                    os.remove(file_path)

            self.logger.error(f'Ошибка в scripts/send_files: {e}')
            print(f'Ошибка в scripts/send_files: {e}')

    #Ежедневная отправка статистики
    async def send_daily_statistics(self):
        try:
            today = date.today()
            yesterday = today - timedelta(days=1)
            active_channels = self.db.get_all_statistics_channel() #получение активных каналов

            # по каждому id активного канала
            for channel_id in active_channels:
                stats = self.db.get_yesterday_statistic(channel_id=channel_id, date=yesterday) # заменить дату на yesterday
                if stats:
                    channel_obj = self.bot.get_channel(channel_id)
                    if channel_obj:
                        await channel_obj.send(f"Статистика за {yesterday}: {stats.message_count} сообщений")
        except Exception as e:
            self.logger.error(f'Ошибка в scripts/send_daily_statistics: {e}')
            print(f'Ошибка в scripts/send_daily_statistics: {e}')