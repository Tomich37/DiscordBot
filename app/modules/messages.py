from datetime import date

class Messages:
    def __init__(self, logger, bot, message):
        self.logger = logger
        self.bot = bot
        self.message = message
        self.db = bot.async_db

    async def process_message(self):
        try:
            if self.message.author == self.bot.user or self.message.guild is None:
                return

            guild_id = self.message.guild.id
            channel_id = self.message.channel.id

            # Общая пользовательская статистика собирается по всему серверу.
            await self.bot.queue_user_message_stat(
                guild_id=guild_id,
                user_id=self.message.author.id,
            )

            # Для каждого активного конкурса канала сохраняем принадлежность поста.
            active_contests = await self.db.get_active_contests_for_channel(guild_id, channel_id)
            for contest in active_contests:
                await self.message.add_reaction(contest.emoji_str)
                await self.db.add_contest_message(contest.id, self.message.id)

            tracker_channel_ids = await self.db.get_all_statistics_channel()
            if channel_id in tracker_channel_ids:
                today = date.today()
                await self.bot.queue_channel_message_stat(
                    channel_id=channel_id,
                    statistic_date=today,
                )
        except Exception as e:
            print(f"Ошибка в messages/process_message: {e}")
            self.logger.exception(f"Ошибка в messages/process_message: {e}")
