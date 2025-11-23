from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine, Column, Integer, String, Boolean, BigInteger, Date, ForeignKey, exc
import os
from dotenv import load_dotenv
import time

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

engine = create_engine(DATABASE_URL)
Base = declarative_base()


def wait_for_db():
    max_retries = 5
    retry_delay = 5  # ожидание между попытками

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
    channel_id = Column(BigInteger)
    emoji_str = Column(String)
    status = Column(Boolean)


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
    channel_id = Column(BigInteger)
    message_id = Column(BigInteger)


class TrackedAnonimusChannel(Base):
    __tablename__ = "tracked_anonimus_channels"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)


class MusicQueue(Base):
    __tablename__ = "music_queue"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, index=True, nullable=False)
    title = Column(String)
    stream_url = Column(String, nullable=False)
    webpage_url = Column(String)


# создание таблиц в БД
Base.metadata.create_all(bind=engine)
Session = sessionmaker(autoflush=False, bind=engine)
