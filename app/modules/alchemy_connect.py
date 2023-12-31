from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import  Column, Integer, String, Boolean, BigInteger
from sqlalchemy.orm import DeclarativeBase
import configparser

config = configparser.ConfigParser()
config.read('./config.ini')
DATABASE_URL = config.get('pg', 'URI')

engine = create_engine(DATABASE_URL)
class Base(DeclarativeBase): pass

class Contests(Base):
    __tablename__ = "contests"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger)
    channel_id = Column(BigInteger,)
    emoji_str = Column(String,)
    status = Column(Boolean,)
  
# создаем таблицы
Base.metadata.create_all(bind=engine)
Session = sessionmaker(autoflush=False, bind=engine)