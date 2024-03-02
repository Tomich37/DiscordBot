from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import  Column, Integer, String, Boolean, BigInteger
from sqlalchemy.orm import DeclarativeBase
import configparser
import os

# config = configparser.ConfigParser()
# config.read('./config.ini')
# DATABASE_URL = config.get('pg', 'URI')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:123QWEmax@localhost:5435/postgres')

engine = create_engine(DATABASE_URL)
class Base(DeclarativeBase): pass

class Contests(Base):
    __tablename__ = "contests"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger)
    channel_id = Column(BigInteger,)
    emoji_str = Column(String,)
    status = Column(Boolean,)

class Recruitments(Base):
    __tablename__ = "recruitments"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger)
    channel_id = Column(BigInteger,)
    message_id = Column(BigInteger,)
  
# создаем таблицы
Base.metadata.create_all(bind=engine)
Session = sessionmaker(autoflush=False, bind=engine)