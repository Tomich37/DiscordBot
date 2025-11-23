from app.modules.alchemy_connect import Session, engine, Contests, TrackedChannel, MessageStatistics, Recruitments, TrackedAnonimusChannel, MusicQueue

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
        
    def create_update_recruitment_channel(self, guild_id, channel_id):
        with Session(autoflush=False, bind=engine) as db:
            # Проверяем, существует ли запись с заданными guild_id
            existing_recruitment = db.query(Recruitments).filter_by(guild_id=guild_id).first()

            if existing_recruitment:
                existing_recruitment.channel_id = channel_id
                db.commit()
            else:
                recruitment = Recruitments(guild_id=guild_id, channel_id=channel_id)
                db.add(recruitment)
                db.commit()
    
    def create_update_recruitment_message(self, guild_id, message_id):
        with Session(autoflush=False, bind=engine) as db:
            # Проверяем, существует ли запись с заданными guild_id
            existing_recruitment = db.query(Recruitments).filter_by(guild_id=guild_id).first()

            if existing_recruitment:
                existing_recruitment.message_id = message_id
                db.commit()
            else:
                recruitment = Recruitments(guild_id=guild_id, message_id=message_id)
                db.add(recruitment)
                db.commit()

    def get_recruitment_by_guild(self, guild_id):
        with Session(autoflush=False, bind=engine) as db:
            recruitment = db.query(Recruitments).filter_by(guild_id=guild_id).first()
            return recruitment
        
    # Обновление статуса отслеживания канала
    def create_update_channel_anonimus(self, guild_id: int, channel_id: int, status: bool):
        with Session(autoflush=False, bind=engine) as db:
            # Проверяем, существует ли запись с заданными guild_id и channel_id
            existing_channel = db.query(TrackedAnonimusChannel).filter_by(guild_id=guild_id, channel_id=channel_id).first()

            if existing_channel:
                # Обновление статуса отслеживания
                existing_channel.is_active = status
            else:
                # Если запись не существует, создаем новую
                statistic = TrackedAnonimusChannel(guild_id=guild_id, channel_id=channel_id, is_active=status)
                db.add(statistic)
            db.commit()

    # Получение всех отслеживаемых каналов для статистики
    def get_all_anonimus_channel(self):
        with Session(autoflush=False, bind=engine) as db:
            channels = db.query(TrackedAnonimusChannel).filter_by(is_active=True).all()
            return [channel.channel_id for channel in channels]

    # Музыкальная очередь
    def add_tracks_to_queue(self, guild_id: int, tracks: list[dict]):
        with Session(autoflush=False, bind=engine) as db:
            for track in tracks:
                db.add(
                    MusicQueue(
                        guild_id=guild_id,
                        title=track.get("title"),
                        stream_url=track.get("stream_url"),
                        webpage_url=track.get("webpage_url"),
                    )
                )
            db.commit()

    def pop_next_track(self, guild_id: int) -> dict | None:
        with Session(autoflush=False, bind=engine) as db:
            entry = (
                db.query(MusicQueue)
                .filter_by(guild_id=guild_id)
                .order_by(MusicQueue.id.asc())
                .first()
            )
            if not entry:
                return None
            track = {
                "id": entry.id,
                "title": entry.title,
                "stream_url": entry.stream_url,
                "webpage_url": entry.webpage_url,
            }
            db.delete(entry)
            db.commit()
            return track

    def clear_queue(self, guild_id: int):
        with Session(autoflush=False, bind=engine) as db:
            db.query(MusicQueue).filter_by(guild_id=guild_id).delete()
            db.commit()
