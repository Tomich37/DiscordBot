from __future__ import annotations

import asyncio
import os
import shutil
import time
from dataclasses import dataclass
from functools import partial
from typing import Optional

import disnake
import imageio_ffmpeg
import yt_dlp
from disnake import voice_client as disnake_voice_client
from disnake.ext import commands


YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "default_search": "ytsearch",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}

FFMPEG_BEFORE_OPTIONS = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
)
FFMPEG_OPTIONS = "-vn"
VOICE_CONNECT_TIMEOUT_SECONDS = 20
MAX_QUEUE_SIZE = 25


def _get_ffmpeg_executable() -> str:
    env_path = os.getenv("FFMPEG_PATH")
    if env_path:
        return env_path

    system_path = shutil.which("ffmpeg")
    if system_path:
        return system_path

    return imageio_ffmpeg.get_ffmpeg_exe()


@dataclass
class Track:
    title: str
    webpage_url: str
    stream_url: str
    duration: Optional[int]
    requested_by: str


class GuildMusicState:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[Track] = asyncio.Queue()
        self.current: Optional[Track] = None
        self.lock = asyncio.Lock()


class MusicCommands(commands.Cog):
    def __init__(self, bot, logger) -> None:
        self.bot = bot
        self.logger = logger
        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        self.ffmpeg_executable = _get_ffmpeg_executable()
        self.guild_states: dict[int, GuildMusicState] = {}
        self.logger.debug(
            "Музыкальный cog загружен | ffmpeg: %s | DAVE: %s | yt-dlp options: %s",
            self.ffmpeg_executable,
            disnake_voice_client.has_dave,
            YTDL_OPTIONS,
        )

    def cog_unload(self) -> None:
        for voice_client in list(self.bot.voice_clients):
            if voice_client.is_connected():
                asyncio.create_task(voice_client.disconnect(force=True))

    def _get_state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self.guild_states:
            self.logger.debug("Музыка: создано состояние очереди для сервера %s", guild_id)
            self.guild_states[guild_id] = GuildMusicState()
        return self.guild_states[guild_id]

    @staticmethod
    def _short_query(query: str, limit: int = 160) -> str:
        query = query.replace("\n", "\\n")
        if len(query) <= limit:
            return query
        return f"{query[:limit]}..."

    @staticmethod
    def _format_duration(duration: Optional[int]) -> str:
        if not duration:
            return "неизвестно"

        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    async def _extract_track(self, query: str, requested_by: str) -> Track:
        loop = asyncio.get_running_loop()
        extract = partial(self.ytdl.extract_info, query, download=False)
        started_at = time.monotonic()
        self.logger.debug("Музыка: начинаю поиск/извлечение трека | query=%s", self._short_query(query))
        data = await loop.run_in_executor(None, extract)
        self.logger.debug(
            "Музыка: yt-dlp вернул данные за %.2f сек | type=%s | has_entries=%s",
            time.monotonic() - started_at,
            data.get("_type"),
            "entries" in data,
        )

        if "entries" in data:
            entries = [entry for entry in data["entries"] if entry]
            self.logger.debug("Музыка: найдено вариантов поиска: %s", len(entries))
            if not entries:
                raise ValueError("По запросу ничего не найдено.")
            data = entries[0]

        stream_url = data.get("url")
        if not stream_url:
            raise ValueError("Не получилось получить аудиопоток.")

        track = Track(
            title=data.get("title") or "Без названия",
            webpage_url=data.get("webpage_url") or data.get("original_url") or query,
            stream_url=stream_url,
            duration=data.get("duration"),
            requested_by=requested_by,
        )
        self.logger.debug(
            "Музыка: трек подготовлен | title=%s | duration=%s | page=%s | stream_host=%s",
            track.title,
            track.duration,
            track.webpage_url,
            stream_url.split("/")[2] if "://" in stream_url else "unknown",
        )
        return track

    async def _ensure_voice_client(
        self,
        inter: disnake.ApplicationCommandInteraction,
    ) -> disnake.VoiceClient:
        author_voice = getattr(inter.author, "voice", None)
        channel = getattr(author_voice, "channel", None)
        if channel is None:
            self.logger.debug(
                "Музыка: пользователь вызвал /play не из голосового канала | user=%s guild=%s",
                inter.author.id,
                inter.guild.id if inter.guild else None,
            )
            raise ValueError("Сначала зайдите в голосовой канал.")

        voice_client = inter.guild.voice_client
        if voice_client and voice_client.channel != channel:
            self.logger.debug(
                "Музыка: перемещаю voice client | guild=%s from=%s to=%s",
                inter.guild.id,
                getattr(voice_client.channel, "id", None),
                channel.id,
            )
            await voice_client.move_to(channel)
            self.logger.debug(
                "Музыка: voice client перемещён | guild=%s channel=%s connected=%s",
                inter.guild.id,
                channel.id,
                voice_client.is_connected(),
            )
            return voice_client

        if voice_client is None:
            if not disnake_voice_client.has_dave:
                self.logger.error(
                    "Музыка: DAVE недоступен, voice-подключение невозможно | "
                    "guild=%s channel=%s package=dave.py",
                    inter.guild.id,
                    channel.id,
                )
                raise ValueError(
                    "Discord требует DAVE/E2EE для голосовых каналов. "
                    "В контейнере не установлен пакет `dave.py`; пересоберите Docker-образ."
                )

            permissions = channel.permissions_for(inter.guild.me)
            self.logger.debug(
                "Музыка: проверка прав voice | guild=%s channel=%s connect=%s speak=%s",
                inter.guild.id,
                channel.id,
                permissions.connect,
                permissions.speak,
            )
            if not permissions.connect or not permissions.speak:
                raise ValueError("У меня нет прав `Подключаться` или `Говорить` в этом канале.")

            started_at = time.monotonic()
            self.logger.debug(
                "Музыка: начинаю подключение к voice | guild=%s channel=%s timeout=%s reconnect=False",
                inter.guild.id,
                channel.id,
                VOICE_CONNECT_TIMEOUT_SECONDS,
            )
            try:
                voice_client = await channel.connect(
                    timeout=VOICE_CONNECT_TIMEOUT_SECONDS,
                    reconnect=False,
                )
            except Exception:
                failed_client = inter.guild.voice_client
                if failed_client:
                    await failed_client.disconnect(force=True)
                self.logger.exception(
                    "Музыка: ошибка подключения к voice | guild=%s channel=%s elapsed=%.2f",
                    inter.guild.id,
                    channel.id,
                    time.monotonic() - started_at,
                )
                raise

            self.logger.debug(
                "Музыка: подключение к voice успешно | guild=%s channel=%s elapsed=%.2f connected=%s",
                inter.guild.id,
                channel.id,
                time.monotonic() - started_at,
                voice_client.is_connected(),
            )
        else:
            self.logger.debug(
                "Музыка: использую существующий voice client | guild=%s channel=%s connected=%s playing=%s paused=%s",
                inter.guild.id,
                getattr(voice_client.channel, "id", None),
                voice_client.is_connected(),
                voice_client.is_playing(),
                voice_client.is_paused(),
            )

        return voice_client

    async def _send_now_playing(
        self,
        channel: disnake.abc.Messageable,
        track: Track,
    ) -> None:
        embed = disnake.Embed(
            title="Сейчас играет",
            description=f"[{track.title}]({track.webpage_url})",
            color=0x00FF00,
        )
        embed.add_field(name="Длительность", value=self._format_duration(track.duration))
        embed.add_field(name="Добавил", value=track.requested_by)
        await channel.send(embed=embed)

    async def _play_next(
        self,
        guild: disnake.Guild,
        text_channel: disnake.abc.Messageable,
    ) -> None:
        state = self._get_state(guild.id)
        voice_client = guild.voice_client

        if voice_client is None or not voice_client.is_connected():
            self.logger.debug(
                "Музыка: следующий трек не запущен, voice client не подключён | guild=%s",
                guild.id,
            )
            state.current = None
            return

        if state.queue.empty():
            self.logger.debug("Музыка: очередь пуста | guild=%s", guild.id)
            state.current = None
            return

        track = await state.queue.get()
        state.current = track
        self.logger.debug(
            "Музыка: запускаю трек | guild=%s channel=%s title=%s queue_left=%s",
            guild.id,
            getattr(voice_client.channel, "id", None),
            track.title,
            state.queue.qsize(),
        )

        source = disnake.FFmpegOpusAudio(
            track.stream_url,
            executable=self.ffmpeg_executable,
            before_options=FFMPEG_BEFORE_OPTIONS,
            options=FFMPEG_OPTIONS,
        )

        def after_play(error: Optional[Exception]) -> None:
            if error:
                self.logger.error(
                    "Музыка: ffmpeg/voice завершился с ошибкой | guild=%s title=%s error=%s",
                    guild.id,
                    track.title,
                    error,
                )
            else:
                self.logger.debug(
                    "Музыка: трек завершён без ошибки | guild=%s title=%s",
                    guild.id,
                    track.title,
                )

            future = asyncio.run_coroutine_threadsafe(
                self._play_next(guild, text_channel),
                self.bot.loop,
            )
            future.add_done_callback(self._log_playback_task_error)

        try:
            voice_client.play(source, after=after_play)
        except Exception:
            self.logger.exception(
                "Музыка: voice_client.play упал до старта | guild=%s title=%s",
                guild.id,
                track.title,
            )
            raise
        self.logger.debug(
            "Музыка: voice_client.play вызван | guild=%s playing=%s paused=%s",
            guild.id,
            voice_client.is_playing(),
            voice_client.is_paused(),
        )
        await self._send_now_playing(text_channel, track)

    def _log_playback_task_error(self, future: asyncio.Future) -> None:
        try:
            future.result()
        except Exception as e:
            self.logger.exception(f"Ошибка запуска следующего трека: {e}")

    @commands.slash_command(
        name="play",
        description="Включить музыку с YouTube или добавить трек в очередь",
    )
    async def play(
        self,
        inter: disnake.ApplicationCommandInteraction,
        query: str = commands.Param(description="Ссылка на YouTube или поисковый запрос"),
    ) -> None:
        if inter.guild is None:
            await inter.response.send_message("Музыка работает только на сервере.", ephemeral=True)
            return

        self.logger.info(
            "Музыка: /play | user=%s guild=%s text_channel=%s query=%s",
            inter.author.id,
            inter.guild.id,
            inter.channel.id if inter.channel else None,
            self._short_query(query),
        )
        await inter.response.defer()

        try:
            voice_client = await self._ensure_voice_client(inter)
            state = self._get_state(inter.guild.id)
            self.logger.debug(
                "Музыка: состояние перед добавлением | guild=%s queue=%s playing=%s paused=%s",
                inter.guild.id,
                state.queue.qsize(),
                voice_client.is_playing(),
                voice_client.is_paused(),
            )

            if state.queue.qsize() >= MAX_QUEUE_SIZE:
                await inter.edit_original_response(
                    f"Очередь переполнена. Максимум треков в очереди: {MAX_QUEUE_SIZE}."
                )
                return

            track = await self._extract_track(query, inter.author.mention)
            async with state.lock:
                await state.queue.put(track)
                queue_position = state.queue.qsize()
                self.logger.debug(
                    "Музыка: трек добавлен в очередь | guild=%s position=%s title=%s",
                    inter.guild.id,
                    queue_position,
                    track.title,
                )

            embed = disnake.Embed(
                title="Добавлено в очередь",
                description=f"[{track.title}]({track.webpage_url})",
                color=0x00FF00,
            )
            embed.add_field(name="Длительность", value=self._format_duration(track.duration))
            embed.add_field(name="Позиция", value=str(queue_position))
            await inter.edit_original_response(embed=embed)

            async with state.lock:
                if not voice_client.is_playing() and not voice_client.is_paused():
                    self.logger.debug("Музыка: плеер свободен, запускаю очередь | guild=%s", inter.guild.id)
                    await self._play_next(inter.guild, inter.channel)
                else:
                    self.logger.debug(
                        "Музыка: плеер уже занят, трек оставлен в очереди | guild=%s playing=%s paused=%s",
                        inter.guild.id,
                        voice_client.is_playing(),
                        voice_client.is_paused(),
                    )
        except ValueError as e:
            self.logger.warning(
                "Музыка: пользовательская ошибка /play | guild=%s user=%s error=%s",
                inter.guild.id,
                inter.author.id,
                e,
            )
            await inter.edit_original_response(str(e))
        except Exception as e:
            self.logger.exception(f"Ошибка в music_commands/play: {e}")
            await inter.edit_original_response(
                "Не получилось включить трек. Проверьте ссылку, доступность видео и ffmpeg.\n"
                f"Техническая причина: `{type(e).__name__}: {str(e)[:300]}`"
            )

    @commands.slash_command(name="skip", description="Пропустить текущий трек")
    async def skip(self, inter: disnake.ApplicationCommandInteraction) -> None:
        voice_client = inter.guild.voice_client if inter.guild else None
        if not voice_client or not (voice_client.is_playing() or voice_client.is_paused()):
            await inter.response.send_message("Сейчас ничего не играет.", ephemeral=True)
            return

        self.logger.info("Музыка: /skip | user=%s guild=%s", inter.author.id, inter.guild.id)
        voice_client.stop()
        await inter.response.send_message("Трек пропущен.")

    @commands.slash_command(name="stop", description="Остановить музыку и очистить очередь")
    async def stop(self, inter: disnake.ApplicationCommandInteraction) -> None:
        if inter.guild is None:
            await inter.response.send_message("Музыка работает только на сервере.", ephemeral=True)
            return

        state = self._get_state(inter.guild.id)
        removed_tracks = state.queue.qsize()
        while not state.queue.empty():
            state.queue.get_nowait()
        state.current = None

        voice_client = inter.guild.voice_client
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()

        self.logger.info(
            "Музыка: /stop | user=%s guild=%s removed_tracks=%s",
            inter.author.id,
            inter.guild.id,
            removed_tracks,
        )
        await inter.response.send_message("Музыка остановлена, очередь очищена.")

    @commands.slash_command(name="pause", description="Поставить музыку на паузу")
    async def pause(self, inter: disnake.ApplicationCommandInteraction) -> None:
        voice_client = inter.guild.voice_client if inter.guild else None
        if not voice_client or not voice_client.is_playing():
            await inter.response.send_message("Сейчас нечего ставить на паузу.", ephemeral=True)
            return

        self.logger.info("Музыка: /pause | user=%s guild=%s", inter.author.id, inter.guild.id)
        voice_client.pause()
        await inter.response.send_message("Пауза.")

    @commands.slash_command(name="resume", description="Продолжить музыку после паузы")
    async def resume(self, inter: disnake.ApplicationCommandInteraction) -> None:
        voice_client = inter.guild.voice_client if inter.guild else None
        if not voice_client or not voice_client.is_paused():
            await inter.response.send_message("Музыка не стоит на паузе.", ephemeral=True)
            return

        self.logger.info("Музыка: /resume | user=%s guild=%s", inter.author.id, inter.guild.id)
        voice_client.resume()
        await inter.response.send_message("Продолжаю.")

    @commands.slash_command(name="queue", description="Показать текущую очередь музыки")
    async def queue(self, inter: disnake.ApplicationCommandInteraction) -> None:
        if inter.guild is None:
            await inter.response.send_message("Музыка работает только на сервере.", ephemeral=True)
            return

        state = self._get_state(inter.guild.id)
        self.logger.debug(
            "Музыка: /queue | user=%s guild=%s current=%s queue=%s",
            inter.author.id,
            inter.guild.id,
            state.current.title if state.current else None,
            state.queue.qsize(),
        )
        lines = []

        if state.current:
            lines.append(f"**Сейчас:** [{state.current.title}]({state.current.webpage_url})")

        queued_tracks = list(state.queue._queue)
        if queued_tracks:
            lines.extend(
                f"`{index}.` [{track.title}]({track.webpage_url}) "
                f"`{self._format_duration(track.duration)}`"
                for index, track in enumerate(queued_tracks[:10], start=1)
            )
            if len(queued_tracks) > 10:
                lines.append(f"И ещё треков: {len(queued_tracks) - 10}")

        if not lines:
            await inter.response.send_message("Очередь пустая.", ephemeral=True)
            return

        embed = disnake.Embed(
            title="Очередь музыки",
            description="\n".join(lines),
            color=0x00FF00,
        )
        await inter.response.send_message(embed=embed)

    @commands.slash_command(name="leave", description="Отключить бота от голосового канала")
    async def leave(self, inter: disnake.ApplicationCommandInteraction) -> None:
        voice_client = inter.guild.voice_client if inter.guild else None
        if not voice_client:
            await inter.response.send_message("Я не подключена к голосовому каналу.", ephemeral=True)
            return

        self.logger.info(
            "Музыка: /leave | user=%s guild=%s channel=%s",
            inter.author.id,
            inter.guild.id,
            getattr(voice_client.channel, "id", None),
        )
        await voice_client.disconnect(force=True)
        if inter.guild:
            self.guild_states.pop(inter.guild.id, None)

        await inter.response.send_message("Отключилась от голосового канала.")


def setup(bot, logger):
    bot.add_cog(MusicCommands(bot, logger))
