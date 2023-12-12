from app.modules.alchemy_connect import Session, engine, Contests

class Database():
    def __init__(self, logger):
        self.logger = logger

    def create_contest(self, guild_id, channel_id, emoji_str, status):
        with Session(autoflush=False, bind=engine) as db:
            # Проверяем, существует ли запись с заданными guild_id и channel_id
            existing_contest = db.query(Contests).filter_by(guild_id=guild_id, channel_id=channel_id).first()

            if existing_contest:
                # Если запись существует, обновляем значения emoji_str и status
                existing_contest.emoji_str = emoji_str
                existing_contest.status = status
                db.commit()
                print(f"Contest updated: {existing_contest.id}")
            else:
                # Если запись не существует, создаем новую
                contest = Contests(guild_id=guild_id, channel_id=channel_id, emoji_str=emoji_str, status=status)
                db.add(contest)
                db.commit()
                print(f"Contest created: {contest.id}")