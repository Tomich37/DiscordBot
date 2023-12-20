from app.modules.alchemy_connect import Session, engine, Contests

class Database():
    def create_update_contest(self, guild_id: int, channel_id: int, emoji_str: str, status: bool):
        with Session(autoflush=False, bind=engine) as db:
            # Проверяем, существует ли запись с заданными guild_id и channel_id
            existing_contest = db.query(Contests).filter_by(guild_id=guild_id, channel_id=channel_id).first()

            if existing_contest:
                # Если запись существует, обновляем значения emoji_str и status
                existing_contest.emoji_str = emoji_str
                existing_contest.status = status
                db.commit()
            else:
                # Если запись не существует, создаем новую
                contest = Contests(guild_id=guild_id, channel_id=channel_id, emoji_str=emoji_str, status=status)
                db.add(contest)
                db.commit()

    def get_all_contests(self):
        with Session(autoflush=False, bind=engine) as db:
            contests = db.query(Contests).all()
            return contests