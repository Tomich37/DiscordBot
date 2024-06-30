from app.modules.alchemy_connect import Session, engine, Contests, TrackedChannel, MessageStatistics

class Database():
    def create_update_contest(self, guild_id: int, channel_id: int, emoji_str: str, status: bool):
        with Session(autoflush=False, bind=engine) as db:
            # Проверяем, существует ли запись с заданными guild_id и channel_id
            existing_contest = db.query(Contests).filter_by(guild_id=guild_id, channel_id=channel_id).first()

            if existing_contest:
                # Если запись существует, обновляем значения emoji_str и status
                existing_contest.emoji_str = emoji_str
                existing_contest.status = status
            else:
                # Если запись не существует, создаем новую
                contest = Contests(guild_id=guild_id, channel_id=channel_id, emoji_str=emoji_str, status=status)
                db.add(contest)
            db.commit()

    def get_all_contests(self):
        with Session(autoflush=False, bind=engine) as db:
            contests = db.query(Contests).all()
            return contests
    
    # Обновление статуса отслеживания канала
    def create_update_channel_statistic(self, guild_id: int, channel_id: int, status: bool):
        with Session(autoflush=False, bind=engine) as db:
            # Проверяем, существует ли запись с заданными guild_id и channel_id
            existing_channel = db.query(TrackedChannel).filter_by(guild_id=guild_id, channel_id=channel_id).first()

            if existing_channel:
                # Обновление статуса отслеживания
                existing_channel.is_active = status
            else:
                # Если запись не существует, создаем новую
                statistic = TrackedChannel(guild_id=guild_id, channel_id=channel_id, is_active=status)
                db.add(statistic)
            db.commit()

    # Получение всех отслеживаемых каналов для статистики
    def get_all_statistics_channel():
        with Session(autoflush=False, bind=engine) as db:
            channels = db.query(TrackedChannel).filter_by(is_active=True).all()
            return [channel.channel_id for channel in channels]

    # Счет сообщений
    def update_message_statistic(self, channel_id: int, today):
        with Session(autoflush=False, bind=engine) as db:
            stat = db.query(MessageStatistics).filter_by(channel_id=channel_id, date=today).first()
            if stat:
                stat.message_count += 1
            else:
                stat = MessageStatistics(channel_id=channel_id, date=today, message_count=0)
                db.add(stat)
            db.commit()

    # Получение всех отслеживаемых каналов для статистики
    def get_yesterday_statistic(channel_id: int, date):
        with Session(autoflush=False, bind=engine) as db:
            stats = db.query(MessageStatistics).filter_by(channel_id=channel_id, date=date).first()
            return stats