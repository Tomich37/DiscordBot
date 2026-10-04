import asyncio
from dataclasses import dataclass
from datetime import date
from time import monotonic
from typing import Any, Callable

from sqlalchemy import select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.alchemy_connect import (
    DATABASE_URL,
    ContestMessage,
    ContestRun,
    MessageStatistics,
    TrackedChannel,
)
from app.modules.database import Database


# Отдельный async-engine обслуживает только неблокирующие запросы. Старый engine
# остаётся доступен репозиторию Database на время постепенной миграции.
async_database_url = make_url(DATABASE_URL)
if async_database_url.drivername.startswith("postgresql"):
    async_database_url = async_database_url.set(drivername="postgresql+asyncpg")

async_engine = create_async_engine(async_database_url, pool_pre_ping=True)
AsyncSession = async_sessionmaker(async_engine, expire_on_commit=False)


@dataclass(frozen=True, slots=True)
class ActiveContest:
    """Минимальный снимок конкурса, безопасный после закрытия сессии."""

    id: int
    emoji_str: str


class AsyncDatabase:
    """Асинхронный фасад БД для Discord-обработчиков.

    Самые частые операции реализованы через AsyncSession. Ещё не перенесённые
    методы Database автоматически выполняются в рабочем потоке и не блокируют
    event loop.
    """

    TRACKED_CHANNELS_CACHE_TTL = 30.0
    ACTIVE_CONTESTS_CACHE_TTL = 5.0

    def __init__(self, sync_database: Database | None = None) -> None:
        self._sync_database = sync_database or Database()
        self._tracked_channels: tuple[float, frozenset[int]] | None = None
        self._active_contests: dict[
            tuple[int, int],
            tuple[float, tuple[ActiveContest, ...]],
        ] = {}
        self._tracked_channels_lock = asyncio.Lock()
        self._active_contests_locks: dict[tuple[int, int], asyncio.Lock] = {}

    def __getattr__(self, name: str) -> Callable[..., Any]:
        """Временно адаптирует старый синхронный метод через asyncio.to_thread."""

        target = getattr(self._sync_database, name)
        if not callable(target):
            raise AttributeError(name)

        async def call_in_thread(*args, **kwargs):
            return await asyncio.to_thread(target, *args, **kwargs)

        return call_in_thread

    async def get_all_statistics_channel(self) -> frozenset[int]:
        now = monotonic()
        cached = self._tracked_channels
        if cached and cached[0] > now:
            return cached[1]

        async with self._tracked_channels_lock:
            now = monotonic()
            cached = self._tracked_channels
            if cached and cached[0] > now:
                return cached[1]

            async with AsyncSession() as session:
                result = await session.execute(
                    select(TrackedChannel.channel_id).where(TrackedChannel.is_active.is_(True))
                )
                channel_ids = frozenset(result.scalars().all())

            self._tracked_channels = (
                now + self.TRACKED_CHANNELS_CACHE_TTL,
                channel_ids,
            )
            return channel_ids

    async def create_update_channel_statistic(
        self,
        guild_id: int,
        channel_id: int,
        status: bool,
    ):
        result = await asyncio.to_thread(
            self._sync_database.create_update_channel_statistic,
            guild_id,
            channel_id,
            status,
        )
        self._tracked_channels = None
        return result

    async def get_active_contests_for_channel(
        self,
        guild_id: int,
        channel_id: int,
    ) -> tuple[ActiveContest, ...]:
        key = (guild_id, channel_id)
        now = monotonic()
        cached = self._active_contests.get(key)
        if cached and cached[0] > now:
            return cached[1]

        lock = self._active_contests_locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = monotonic()
            cached = self._active_contests.get(key)
            if cached and cached[0] > now:
                return cached[1]

            async with AsyncSession() as session:
                result = await session.execute(
                    select(ContestRun.id, ContestRun.emoji_str).where(
                        ContestRun.guild_id == guild_id,
                        ContestRun.channel_id == channel_id,
                        ContestRun.is_active.is_(True),
                    )
                )
                contests = tuple(
                    ActiveContest(id=contest_id, emoji_str=emoji_str)
                    for contest_id, emoji_str in result.all()
                )

            self._active_contests[key] = (
                now + self.ACTIVE_CONTESTS_CACHE_TTL,
                contests,
            )
            return contests

    async def start_contest_run(self, *args, **kwargs):
        result = await asyncio.to_thread(
            self._sync_database.start_contest_run,
            *args,
            **kwargs,
        )
        self._invalidate_contest_cache(args, kwargs)
        return result

    async def stop_contest_run(self, *args, **kwargs):
        result = await asyncio.to_thread(
            self._sync_database.stop_contest_run,
            *args,
            **kwargs,
        )
        self._invalidate_contest_cache(args, kwargs)
        return result

    def _invalidate_contest_cache(self, args: tuple, kwargs: dict) -> None:
        guild_id = kwargs.get("guild_id", args[0] if len(args) > 0 else None)
        channel_id = kwargs.get("channel_id", args[1] if len(args) > 1 else None)
        if guild_id is not None and channel_id is not None:
            self._active_contests.pop((guild_id, channel_id), None)

    async def add_contest_message(self, contest_id: int, message_id: int) -> None:
        async with AsyncSession() as session:
            existing = await session.scalar(
                select(ContestMessage.id).where(
                    ContestMessage.contest_id == contest_id,
                    ContestMessage.message_id == message_id,
                )
            )
            if existing is not None:
                return

            session.add(ContestMessage(contest_id=contest_id, message_id=message_id))
            await session.commit()

    async def bulk_increment_channel_message_counts(
        self,
        counters: dict[tuple[int, date], int],
    ) -> None:
        """Записывает накопленные счётчики одним коммитом."""

        if not counters:
            return

        async with AsyncSession() as session:
            for (channel_id, statistic_date), count in counters.items():
                result = await session.execute(
                    update(MessageStatistics)
                    .where(
                        MessageStatistics.channel_id == channel_id,
                        MessageStatistics.date == statistic_date,
                    )
                    .values(message_count=MessageStatistics.message_count + count)
                )
                if result.rowcount == 0:
                    session.add(
                        MessageStatistics(
                            channel_id=channel_id,
                            date=statistic_date,
                            message_count=count,
                        )
                    )

            await session.commit()

    async def dispose(self) -> None:
        await async_engine.dispose()
