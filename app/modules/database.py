from app.modules.alchemy_connect import (
    ContestMessage,
    ContestRun,
    Contests,
    MessageStatistics,
    Recruitments,
    Session,
    TrackedAnonimusChannel,
    TrackedChannel,
    engine,
)


class Database:
    def create_update_contest(self, guild_id: int, channel_id: int, emoji_str: str, status: bool):
        with Session(autoflush=False, bind=engine) as db:
            # Старую таблицу сохраняем для обратной совместимости.
            existing_contest = db.query(Contests).filter_by(guild_id=guild_id, channel_id=channel_id).first()

            if existing_contest:
                existing_contest.emoji_str = emoji_str
                existing_contest.status = status
            else:
                contest = Contests(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    emoji_str=emoji_str,
                    status=status,
                )
                db.add(contest)

            db.commit()

    def start_contest_run(self, guild_id: int, channel_id: int, contest_name: str, emoji_str: str):
        with Session(autoflush=False, bind=engine) as db:
            contest = (
                db.query(ContestRun)
                .filter_by(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                    is_active=True,
                )
                .first()
            )

            if contest:
                contest.emoji_str = emoji_str
            else:
                contest = ContestRun(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                    emoji_str=emoji_str,
                    is_active=True,
                )
                db.add(contest)
                db.flush()

            db.commit()
            db.refresh(contest)
            return contest

    def stop_contest_run(self, guild_id: int, channel_id: int, contest_name: str):
        with Session(autoflush=False, bind=engine) as db:
            contest = (
                db.query(ContestRun)
                .filter_by(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                    is_active=True,
                )
                .first()
            )

            if not contest:
                return None

            contest.is_active = False
            db.commit()
            db.refresh(contest)
            return contest

    def get_active_contests_for_channel(self, guild_id: int, channel_id: int):
        with Session(autoflush=False, bind=engine) as db:
            return (
                db.query(ContestRun)
                .filter_by(guild_id=guild_id, channel_id=channel_id, is_active=True)
                .all()
            )

    def add_contest_message(self, contest_id: int, message_id: int):
        with Session(autoflush=False, bind=engine) as db:
            existing_message = (
                db.query(ContestMessage)
                .filter_by(contest_id=contest_id, message_id=message_id)
                .first()
            )

            if existing_message:
                return existing_message

            contest_message = ContestMessage(contest_id=contest_id, message_id=message_id)
            db.add(contest_message)
            db.commit()
            db.refresh(contest_message)
            return contest_message

    def get_contest_messages(self, contest_id: int):
        with Session(autoflush=False, bind=engine) as db:
            return (
                db.query(ContestMessage)
                .filter_by(contest_id=contest_id)
                .order_by(ContestMessage.id.asc())
                .all()
            )

    # Обновление статуса отслеживания канала.
    def create_update_channel_statistic(self, guild_id: int, channel_id: int, status: bool):
        with Session(autoflush=False, bind=engine) as db:
            existing_channel = db.query(TrackedChannel).filter_by(guild_id=guild_id, channel_id=channel_id).first()

            if existing_channel:
                existing_channel.is_active = status
            else:
                statistic = TrackedChannel(guild_id=guild_id, channel_id=channel_id, is_active=status)
                db.add(statistic)

            db.commit()

    # Получение всех отслеживаемых каналов для статистики.
    def get_all_statistics_channel():
        with Session(autoflush=False, bind=engine) as db:
            channels = db.query(TrackedChannel).filter_by(is_active=True).all()
            return [channel.channel_id for channel in channels]

    # Счёт сообщений.
    def update_message_statistic(self, channel_id: int, today):
        with Session(autoflush=False, bind=engine) as db:
            stat = db.query(MessageStatistics).filter_by(channel_id=channel_id, date=today).first()
            if stat:
                stat.message_count += 1
            else:
                stat = MessageStatistics(channel_id=channel_id, date=today, message_count=0)
                db.add(stat)

            db.commit()

    def get_yesterday_statistic(channel_id: int, date):
        with Session(autoflush=False, bind=engine) as db:
            stats = db.query(MessageStatistics).filter_by(channel_id=channel_id, date=date).first()
            return stats

    def create_update_recruitment_channel(self, guild_id, channel_id):
        with Session(autoflush=False, bind=engine) as db:
            existing_recruitment = db.query(Recruitments).filter_by(guild_id=guild_id).first()

            if existing_recruitment:
                existing_recruitment.channel_id = channel_id
            else:
                recruitment = Recruitments(guild_id=guild_id, channel_id=channel_id)
                db.add(recruitment)

            db.commit()

    def create_update_recruitment_message(self, guild_id, message_id):
        with Session(autoflush=False, bind=engine) as db:
            existing_recruitment = db.query(Recruitments).filter_by(guild_id=guild_id).first()

            if existing_recruitment:
                existing_recruitment.message_id = message_id
            else:
                recruitment = Recruitments(guild_id=guild_id, message_id=message_id)
                db.add(recruitment)

            db.commit()

    def get_recruitment_by_guild(self, guild_id):
        with Session(autoflush=False, bind=engine) as db:
            recruitment = db.query(Recruitments).filter_by(guild_id=guild_id).first()
            return recruitment

    # Обновление статуса отслеживания анонимного канала.
    def create_update_channel_anonimus(self, guild_id: int, channel_id: int, status: bool):
        with Session(autoflush=False, bind=engine) as db:
            existing_channel = (
                db.query(TrackedAnonimusChannel)
                .filter_by(guild_id=guild_id, channel_id=channel_id)
                .first()
            )

            if existing_channel:
                existing_channel.is_active = status
            else:
                statistic = TrackedAnonimusChannel(guild_id=guild_id, channel_id=channel_id, is_active=status)
                db.add(statistic)

            db.commit()

    # Получение всех анонимных каналов.
    def get_all_anonimus_channel(self):
        with Session(autoflush=False, bind=engine) as db:
            channels = db.query(TrackedAnonimusChannel).filter_by(is_active=True).all()
            return [channel.channel_id for channel in channels]
