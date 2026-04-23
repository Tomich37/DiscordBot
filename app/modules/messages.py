from datetime import date

from app.modules.database import Database


class Messages:
    def __init__(self, logger, bot, message):
        self.logger = logger
        self.bot = bot
        self.message = message
        self.db = Database()

    async def process_message(self):
        try:
            tracker_channel_dict = Database.get_all_statistics_channel()

            if self.message.author == self.bot.user:
                return

            guild_id = self.message.guild.id
            channel_id = self.message.channel.id

            # Для каждого активного конкурса канала сохраняем принадлежность поста.
            active_contests = self.db.get_active_contests_for_channel(guild_id, channel_id)
            for contest in active_contests:
                await self.message.add_reaction(contest.emoji_str)
                self.db.add_contest_message(contest.id, self.message.id)

            if channel_id in tracker_channel_dict:
                today = date.today()
                self.db.update_message_statistic(channel_id=channel_id, today=today)
        except Exception as e:
            print(f"Ошибка в messages/process_message: {e}")
            self.logger.exception(f"Ошибка в messages/process_message: {e}")
