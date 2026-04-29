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


class GuildUserStats(Base):
    __tablename__ = "guild_user_stats"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_guild_user_stats"),
    )

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    message_count = Column(Integer, default=0, nullable=False)
    total_voice_seconds = Column(Integer, default=0, nullable=False)
    stats_started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    current_voice_channel_id = Column(BigInteger, nullable=True)
    voice_joined_at = Column(DateTime, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MusicPlaylist(Base):
    __tablename__ = "music_playlists"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MusicPlaylistTrack(Base):
    __tablename__ = "music_playlist_tracks"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("music_playlists.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False, index=True)
    title = Column(String, nullable=False)
    webpage_url = Column(Text, nullable=False)
    duration = Column(Integer, nullable=True)
    status = Column(String(20), default="pending", nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlchemyPlayer(Base):
    __tablename__ = "alchemy_players"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_alchemy_player"),
    )

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    balance = Column(Integer, default=0, nullable=False)
    first_discovery_count = Column(Integer, default=0, nullable=False)
    last_daily_at = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlchemyElement(Base):
    __tablename__ = "alchemy_elements"
    __table_args__ = (
        UniqueConstraint("guild_id", "normalized_name", name="uq_alchemy_element"),
    )

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    normalized_name = Column(String(80), nullable=False, index=True)
    display_name = Column(String(80), nullable=False)
    first_discoverer_id = Column(BigInteger, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlchemyRecipe(Base):
    __tablename__ = "alchemy_recipes"
    __table_args__ = (
        UniqueConstraint("guild_id", "left_element", "right_element", name="uq_alchemy_recipe_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    left_element = Column(String(80), nullable=False, index=True)
    right_element = Column(String(80), nullable=False, index=True)
    result_element_id = Column(Integer, ForeignKey("alchemy_elements.id"), nullable=False, index=True)
    first_discoverer_id = Column(BigInteger, nullable=False, index=True)
    openai_response_id = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlchemyGuildDiscovery(Base):
    __tablename__ = "alchemy_guild_discoveries"
    __table_args__ = (
        UniqueConstraint("guild_id", "recipe_id", name="uq_alchemy_guild_discovery"),
    )

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    recipe_id = Column(Integer, ForeignKey("alchemy_recipes.id"), nullable=False, index=True)
    first_discoverer_id = Column(BigInteger, nullable=False, index=True)
    discovered_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlchemyPlayerElement(Base):
    __tablename__ = "alchemy_player_elements"
    __table_args__ = (
        UniqueConstraint("player_id", "element_id", name="uq_alchemy_player_element"),
    )

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("alchemy_players.id"), nullable=False, index=True)
    element_id = Column(Integer, ForeignKey("alchemy_elements.id"), nullable=False, index=True)
    discovered_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlchemyTransaction(Base):
    __tablename__ = "alchemy_transactions"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("alchemy_players.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    reason = Column(String(40), nullable=False, index=True)
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


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

    if "guild_user_stats" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("guild_user_stats")}
        with engine.begin() as connection:
            if "stats_started_at" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE guild_user_stats "
                        "ADD COLUMN stats_started_at TIMESTAMP NOT NULL DEFAULT NOW()"
                    )
                )


# Создаём таблицы и добавляем недостающие колонки для уже существующей БД.
Base.metadata.create_all(bind=engine)
ensure_schema_updates()
Session = sessionmaker(autoflush=False, bind=engine)
