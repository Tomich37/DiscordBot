from app.modules.database import Database
from app.modules.scripts import Scripts
from datetime import date

class Messages:        
    def __init__(self, logger, bot, message):
            self.logger = logger            
            self.bot = bot
            self.message = message
            self.db = Database()
            self.sc = Scripts(logger=logger, bot=bot)

            self.all_contests = self.contests_info()

    def contests_info(self):
        try:             
            all_contests = self.db.get_all_contests()
            contests_dict = {}

            for contest in all_contests:
                key = (contest.guild_id, contest.channel_id)
                value = {
                    'id': contest.id,
                    'emoji_str': contest.emoji_str,
                    'status': contest.status
                }
                contests_dict[key] = value

            return contests_dict
        except Exception as e:
            self.logger.error(f'Ошибка в messages/contests_info: {e}')

    async def process_message(self):
        try:  
            tracker_channel_dict = Database.get_all_statistics_channel() # получение отслеживаемых каналов
            # Если сообщение от пользователя
            if self.message.author != self.bot.user:
                guild_id = self.message.guild.id
                channel_id = self.message.channel.id

                # Проверяем наличие гильдии и канала в хеш-таблице contests_dict
                if (guild_id, channel_id) in self.all_contests:
                    contest_info = self.all_contests[(guild_id, channel_id)]
                    emoji_str = contest_info['emoji_str']
                    status = contest_info['status']

                    if status:
                        await self.message.add_reaction(emoji_str)
                
                # Проверка есть ли канал в отслеживаемых для статистики
                if (channel_id) in tracker_channel_dict:
                    today = date.today()
                    self.db.update_message_statistic(channel_id=channel_id, today=today)
        except Exception as e:
            print(f'Ошибка в messages/process_message: {e}')
            self.logger.error(f'Ошибка в messages/process_message: {e}')
