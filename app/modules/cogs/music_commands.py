from __future__ import annotations

import asyncio
import os
import shutil
import time
from dataclasses import dataclass
from functools import partial
from typing import Optional
from urllib.parse import parse_qs, urlparse

import disnake
import imageio_ffmpeg
import yt_dlp
from disnake import voice_client as disnake_voice_client
from disnake.ext import commands


YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "default_search": "ytsearch",
    "noplaylist": True,
    "ignoreerrors": True,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}
YTDL_PLAYLIST_OPTIONS = {
    "extract_flat": "in_playlist",
    "ignoreerrors": True,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}

FFMPEG_BEFORE_OPTIONS = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
)
FFMPEG_OPTIONS = "-vn"
VOICE_CONNECT_TIMEOUT_SECONDS = 20
MAX_QUEUE_SIZE = 200


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
    db_track_id: int
    owner_id: int
    position: int
    title: str
    webpage_url: str
    stream_url: str
    duration: Optional[int]
    requested_by: str


class GuildMusicState:
    def __init__(self) -> None:
        self.current: Optional[Track] = None
        self.owner_id: Optional[int] = None
        self.stop_reason: Optional[str] = None
        self.lock = asyncio.Lock()


class MusicCommands(commands.Cog):
    def __init__(self, bot, logger) -> None:
        self.bot = bot
        self.logger = logger
        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        self.playlist_ytdl = yt_dlp.YoutubeDL(YTDL_PLAYLIST_OPTIONS)
        self.ffmpeg_executable = _get_ffmpeg_executable()
        self.guild_states: dict[int, GuildMusicState] = {}
        self.bot.db.reset_music_playing_tracks()
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

    @staticmethod
    def _has_playlist_marker(query: str) -> bool:
        parsed_url = urlparse(query)
        query_params = parse_qs(parsed_url.query)
        return bool(query_params.get("list")) or "/playlist" in parsed_url.path

    @staticmethod
    def _is_playlist_result(query: str, data: dict) -> bool:
        if not data or "entries" not in data:
            return False

        extractor = str(data.get("extractor") or "").lower()
        extractor_key = str(data.get("extractor_key") or "").lower()
        if "search" in extractor or "search" in extractor_key:
            return False

        return (
            MusicCommands._has_playlist_marker(query)
            or data.get("_type") in {"playlist", "multi_video"}
            or "playlist" in extractor
            or "playlist" in extractor_key
            or extractor_key == "youtubetab"
        )

    @staticmethod
    def _entry_webpage_url(entry: dict, query: str) -> str:
        webpage_url = entry.get("webpage_url") or entry.get("original_url")
        if webpage_url:
            return webpage_url

        entry_url = entry.get("url")
        if not entry_url:
            return query

        if str(entry_url).startswith("http"):
            return entry_url

        extractor_key = str(entry.get("extractor_key") or "").lower()
        if "youtube" in extractor_key and len(str(entry_url)) == 11:
            return f"https://www.youtube.com/watch?v={entry_url}"

        return str(entry_url)

    def _build_music_item(self, entry: dict, query: str) -> dict:
        return {
            "title": entry.get("title") or "Без названия",
            "webpage_url": self._entry_webpage_url(entry, query),
            "duration": entry.get("duration"),
        }

    def _build_track(self, db_track: dict, data: dict, requested_by: str) -> Track:
        stream_url = data.get("url")
        if not stream_url:
            raise ValueError("Не получилось получить аудиопоток.")

        return Track(
            db_track_id=db_track["id"],
            owner_id=db_track["user_id"],
            position=db_track["position"],
            title=data.get("title") or "Без названия",
            webpage_url=data.get("webpage_url") or data.get("original_url") or db_track["webpage_url"],
            stream_url=stream_url,
            duration=data.get("duration") or db_track.get("duration"),
            requested_by=requested_by,
        )

    def _extract_music_items_sync(self, query: str) -> list[dict]:
        ytdl = self.playlist_ytdl if self._has_playlist_marker(query) else self.ytdl
        data = ytdl.extract_info(query, download=False)
        self.logger.debug(
            "Музыка: yt-dlp вернул данные | type=%s | extractor=%s | extractor_key=%s | has_entries=%s",
            data.get("_type") if data else None,
            data.get("extractor") if data else None,
            data.get("extractor_key") if data else None,
            bool(data and "entries" in data),
        )

        if not data:
            raise ValueError("По запросу ничего не найдено.")

        if "entries" not in data:
            return [self._build_music_item(data, query)]

        entries = [entry for entry in data["entries"] if entry]
        self.logger.debug(
            "Музыка: найдено элементов в ответе yt-dlp | count=%s | playlist=%s",
            len(entries),
            self._is_playlist_result(query, data),
        )
        if not entries:
            raise ValueError("По запросу ничего не найдено.")

        if not self._is_playlist_result(query, data):
            return [self._build_music_item(entries[0], query)]

        return [self._build_music_item(entry, query) for entry in entries]

    async def _extract_music_items(self, query: str) -> list[dict]:
        loop = asyncio.get_running_loop()
        extract = partial(self._extract_music_items_sync, query)
        started_at = time.monotonic()
        self.logger.debug("Музыка: начинаю чтение треков | query=%s", self._short_query(query))
        data = await loop.run_in_executor(None, extract)
        self.logger.debug(
            "Музыка: получены элементы плейлиста за %.2f сек | count=%s",
            time.monotonic() - started_at,
            len(data),
        )
        return data

    async def _prepare_track(self, db_track: dict, requested_by: str) -> Track:
        loop = asyncio.get_running_loop()
        started_at = time.monotonic()
        self.logger.debug(
            "Музыка: готовлю трек к проигрыванию | db_track=%s position=%s url=%s",
            db_track["id"],
            db_track["position"],
            db_track["webpage_url"],
        )
        extract = partial(self.ytdl.extract_info, db_track["webpage_url"], download=False)
        data = await loop.run_in_executor(None, extract)
        if "entries" in data:
            entries = [entry for entry in data["entries"] if entry]
            if not entries:
                raise ValueError("По запросу ничего не найдено.")
            data = entries[0]

        track = self._build_track(db_track, data, requested_by)
        self.logger.debug(
            "Музыка: трек готов за %.2f сек | db_track=%s title=%s stream_host=%s",
            time.monotonic() - started_at,
            db_track["id"],
            track.title,
            track.stream_url.split("/")[2] if "://" in track.stream_url else "unknown",
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

        if state.owner_id is None:
            self.logger.debug("Музыка: владелец плейлиста не выбран | guild=%s", guild.id)
            state.current = None
            return

        requested_by = f"<@{state.owner_id}>"
        track = None
        while track is None:
            db_track = self.bot.db.get_next_music_track(guild.id, state.owner_id)
            if not db_track:
                self.logger.debug(
                    "Музыка: в БД нет следующих треков | guild=%s owner=%s",
                    guild.id,
                    state.owner_id,
                )
                state.current = None
                return

            try:
                self.bot.db.mark_music_track_status(db_track["id"], "playing")
                track = await self._prepare_track(db_track, requested_by)
            except Exception as e:
                self.bot.db.mark_music_track_status(db_track["id"], "error", str(e)[:1000])
                self.logger.warning(
                    "Музыка: трек из плейлиста недоступен и будет пропущен | guild=%s owner=%s db_track=%s error=%s",
                    guild.id,
                    state.owner_id,
                    db_track["id"],
                    e,
                )

        state.current = track
        self.logger.debug(
            "Музыка: запускаю трек | guild=%s channel=%s owner=%s db_track=%s position=%s title=%s",
            guild.id,
            getattr(voice_client.channel, "id", None),
            track.owner_id,
            track.db_track_id,
            track.position,
            track.title,
        )

        source = disnake.FFmpegOpusAudio(
            track.stream_url,
            executable=self.ffmpeg_executable,
            before_options=FFMPEG_BEFORE_OPTIONS,
            options=FFMPEG_OPTIONS,
        )

        def after_play(error: Optional[Exception]) -> None:
            stop_reason = state.stop_reason
            state.stop_reason = None
            if error:
                status = "error"
                error_message = str(error)[:1000]
                if stop_reason == "leave":
                    status = "pending"
                    error_message = None
                elif stop_reason in {"skip", "stop"}:
                    status = "skipped"
                    error_message = None
                self.bot.db.mark_music_track_status(track.db_track_id, status, error_message)
                self.logger.error(
                    "Музыка: ffmpeg/voice завершился с ошибкой | guild=%s title=%s status=%s error=%s",
                    guild.id,
                    track.title,
                    status,
                    error,
                )
            else:
                status = "skipped" if stop_reason in {"skip", "stop"} else "played"
                if stop_reason == "leave":
                    status = "pending"
                self.bot.db.mark_music_track_status(track.db_track_id, status)
                self.logger.debug(
                    "Музыка: трек завершён | guild=%s title=%s status=%s",
                    guild.id,
                    track.title,
                    status,
                )

            if stop_reason in {"stop", "leave"}:
                state.current = None
                return

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
        query: Optional[str] = commands.Param(
            default=None,
            description="Ссылка на YouTube, плейлист или поиск. Если пусто, продолжит ваш плейлист.",
        ),
    ) -> None:
        if inter.guild is None:
            await inter.response.send_message("Музыка работает только на сервере.", ephemeral=True)
            return

        self.logger.info(
            "Музыка: /play | user=%s guild=%s text_channel=%s query=%s",
            inter.author.id,
            inter.guild.id,
            inter.channel.id if inter.channel else None,
            self._short_query(query or ""),
        )
        await inter.response.defer()

        try:
            voice_client = await self._ensure_voice_client(inter)
            state = self._get_state(inter.guild.id)
            playlist_stats = self.bot.db.get_music_playlist_stats(inter.guild.id, inter.author.id)
            self.logger.debug(
                "Музыка: состояние перед добавлением | guild=%s owner=%s pending=%s playing=%s paused=%s",
                inter.guild.id,
                inter.author.id,
                playlist_stats["pending_count"],
                voice_client.is_playing(),
                voice_client.is_paused(),
            )

            if query:
                free_slots = MAX_QUEUE_SIZE - playlist_stats["pending_count"]
                if free_slots <= 0:
                    await inter.edit_original_response(
                        f"Очередь переполнена. Максимум треков в очереди: {MAX_QUEUE_SIZE}."
                    )
                    return

                music_items = await self._extract_music_items(query)
                skipped_tracks = max(len(music_items) - free_slots, 0)
                items_to_add = music_items[:free_slots]
                append_result = self.bot.db.append_music_tracks(
                    inter.guild.id,
                    inter.author.id,
                    items_to_add,
                )
                first_position = append_result.get("first_position", 1)
                self.logger.debug(
                    "Музыка: треки сохранены в БД | guild=%s owner=%s added=%s skipped=%s first_position=%s",
                    inter.guild.id,
                    inter.author.id,
                    len(items_to_add),
                    skipped_tracks,
                    first_position,
                )

                first_track = items_to_add[0]
                embed = disnake.Embed(
                    title="Добавлено в личный плейлист",
                    description=(
                        f"[{first_track['title']}]({first_track['webpage_url']})"
                        if len(items_to_add) == 1
                        else f"Добавлено треков: **{len(items_to_add)}**"
                    ),
                    color=0x00FF00,
                )
                if len(items_to_add) == 1:
                    embed.add_field(name="Длительность", value=self._format_duration(first_track.get("duration")))
                else:
                    embed.add_field(
                        name="Первый трек",
                        value=f"[{first_track['title']}]({first_track['webpage_url']})",
                    )
                embed.add_field(name="Позиция", value=str(first_position))
                if skipped_tracks:
                    embed.add_field(
                        name="Не добавлено",
                        value=f"{skipped_tracks} треков не поместились в очередь.",
                        inline=False,
                    )
                await inter.edit_original_response(embed=embed)
            else:
                if playlist_stats["pending_count"] <= 0:
                    await inter.edit_original_response("В вашем личном плейлисте нет треков для продолжения.")
                    return

                await inter.edit_original_response(
                    f"Продолжаю ваш личный плейлист. Осталось треков: `{playlist_stats['pending_count']}`."
                )

            async with state.lock:
                if not voice_client.is_playing() and not voice_client.is_paused():
                    state.owner_id = inter.author.id
                    self.logger.debug(
                        "Музыка: плеер свободен, запускаю личный плейлист | guild=%s owner=%s",
                        inter.guild.id,
                        state.owner_id,
                    )
                    await self._play_next(inter.guild, inter.channel)
                elif state.owner_id == inter.author.id:
                    self.logger.debug(
                        "Музыка: плеер уже проигрывает плейлист этого пользователя | guild=%s owner=%s",
                        inter.guild.id,
                        state.owner_id,
                    )
                else:
                    self.logger.debug(
                        "Музыка: плеер занят другим плейлистом, треки сохранены для будущего запуска | "
                        "guild=%s current_owner=%s requester=%s playing=%s paused=%s",
                        inter.guild.id,
                        state.owner_id,
                        inter.author.id,
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
        state = self._get_state(inter.guild.id)
        state.stop_reason = "skip"
        voice_client.stop()
        await inter.response.send_message("Трек пропущен.")

    @commands.slash_command(name="stop", description="Остановить музыку и очистить очередь")
    async def stop(self, inter: disnake.ApplicationCommandInteraction) -> None:
        if inter.guild is None:
            await inter.response.send_message("Музыка работает только на сервере.", ephemeral=True)
            return

        state = self._get_state(inter.guild.id)
        target_user_id = state.owner_id or inter.author.id
        removed_tracks = self.bot.db.clear_music_playlist(inter.guild.id, target_user_id)
        state.current = None

        voice_client = inter.guild.voice_client
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            state.stop_reason = "stop"
            voice_client.stop()

        self.logger.info(
            "Музыка: /stop | user=%s guild=%s target_user=%s removed_tracks=%s",
            inter.author.id,
            inter.guild.id,
            target_user_id,
            removed_tracks,
        )
        await inter.response.send_message("Музыка остановлена, личный плейлист очищен.")

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
        playlist_stats = self.bot.db.get_music_playlist_stats(inter.guild.id, inter.author.id)
        self.logger.debug(
            "Музыка: /queue | user=%s guild=%s current=%s pending=%s",
            inter.author.id,
            inter.guild.id,
            state.current.title if state.current else None,
            playlist_stats["pending_count"],
        )
        lines = []

        if state.current:
            lines.append(f"**Сейчас:** [{state.current.title}]({state.current.webpage_url})")

        if playlist_stats["pending_count"]:
            lines.append(f"**В вашем личном плейлисте осталось:** `{playlist_stats['pending_count']}`")
            if playlist_stats["error_count"]:
                lines.append(f"**Недоступных треков пропущено:** `{playlist_stats['error_count']}`")

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
        state = self._get_state(inter.guild.id)
        state.stop_reason = "leave"
        await voice_client.disconnect(force=True)
        if inter.guild:
            self.guild_states.pop(inter.guild.id, None)

        await inter.response.send_message("Отключилась от голосового канала.")


def setup(bot, logger):
    bot.add_cog(MusicCommands(bot, logger))
