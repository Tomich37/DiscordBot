from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine, Column, Integer, String, Boolean, BigInteger, Date, ForeignKey
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

engine = create_engine(DATABASE_URL)
Base = declarative_base()

class Contests(Base):
    __tablename__ = "contests"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger)
    channel_id = Column(BigInteger,)
    emoji_str = Column(String,)
    status = Column(Boolean,)

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
  
# создаем таблицы
Base.metadata.create_all(bind=engine)
Session = sessionmaker(autoflush=False, bind=engine)