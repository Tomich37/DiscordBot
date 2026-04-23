from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    exc,
    inspect,
    text,
)
import os
from dotenv import load_dotenv
import time
from datetime import datetime

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

engine = create_engine(DATABASE_URL)
Base = declarative_base()

def wait_for_db():
    max_retries = 5
    retry_delay = 5  # секунды
    
    for attempt in range(max_retries):
        try:
            engine.connect()
            print("Database is ready!")
            return True
        except exc.OperationalError:
            print(f"Database not ready, waiting {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)
    
    print("Failed to connect to database after multiple attempts")
    return False

if not wait_for_db():
    exit(1)

class Contests(Base):
    __tablename__ = "contests"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger)
    channel_id = Column(BigInteger,)
    emoji_str = Column(String,)
    status = Column(Boolean,)


class ContestRun(Base):
    __tablename__ = "contest_runs"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    contest_name = Column(String, nullable=False)
    emoji_str = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class ContestMessage(Base):
    __tablename__ = "contest_messages"
    __table_args__ = (
        UniqueConstraint("contest_id", "message_id", name="uq_contest_message"),
    )

    id = Column(Integer, primary_key=True, index=True)
    contest_id = Column(Integer, ForeignKey("contest_runs.id"), nullable=False, index=True)
    message_id = Column(BigInteger, nullable=False, index=True)


class Giveaway(Base):
    __tablename__ = "giveaways"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_giveaway_message"),
    )

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    message_id = Column(BigInteger, nullable=False, index=True)
    admin_channel_id = Column(BigInteger, nullable=True, index=True)
    admin_message_id = Column(BigInteger, nullable=True, index=True)
    creator_id = Column(BigInteger, nullable=False)
    emoji_str = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    winner_count = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)


class GiveawayParticipant(Base):
    __tablename__ = "giveaway_participants"
    __table_args__ = (
        UniqueConstraint("giveaway_id", "user_id", name="uq_giveaway_participant"),
    )

    id = Column(Integer, primary_key=True, index=True)
    giveaway_id = Column(Integer, ForeignKey("giveaways.id"), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    left_at = Column(DateTime, nullable=True)


class GiveawayWin(Base):
    __tablename__ = "giveaway_wins"

    id = Column(Integer, primary_key=True, index=True)
    giveaway_id = Column(Integer, ForeignKey("giveaways.id"), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    won_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TrackedChannel(Base):
    __tablename__ = "tracked_channels"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)

class MessageStatistics(Base):
    __tablename__ = "message_statistics"
    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(BigInteger, ForeignKey('tracked_channels.channel_id'), nullable=False)
    date = Column(Date, nullable=False)
    message_count = Column(Integer, default=0)

class Recruitments(Base):
    __tablename__ = "recruitments"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger)
    channel_id = Column(BigInteger,)
    message_id = Column(BigInteger,)


class RecruitmentPosition(Base):
    __tablename__ = "recruitment_positions"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    title = Column(String(100), nullable=False)
    description = Column(String(100), nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)


class RecruitmentQuestion(Base):
    __tablename__ = "recruitment_questions"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    label = Column(String(45), nullable=False)
    placeholder = Column(String(100), nullable=False)
    style = Column(String(20), default="paragraph", nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)


class TrackedAnonimusChannel(Base):
    __tablename__ = "tracked_anonimus_channels"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
  
def ensure_schema_updates():
    inspector = inspect(engine)

    if "giveaways" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("giveaways")}
        with engine.begin() as connection:
            if "admin_channel_id" not in columns:
                connection.execute(text("ALTER TABLE giveaways ADD COLUMN admin_channel_id BIGINT"))
            if "admin_message_id" not in columns:
                connection.execute(text("ALTER TABLE giveaways ADD COLUMN admin_message_id BIGINT"))

    if "giveaway_participants" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("giveaway_participants")}
        with engine.begin() as connection:
            if "is_active" not in columns:
                connection.execute(
                    text("ALTER TABLE giveaway_participants ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE")
                )
            if "left_at" not in columns:
                connection.execute(text("ALTER TABLE giveaway_participants ADD COLUMN left_at TIMESTAMP"))


# Создаём таблицы и добавляем недостающие колонки для уже существующей БД.
Base.metadata.create_all(bind=engine)
ensure_schema_updates()
Session = sessionmaker(autoflush=False, bind=engine)
