import asyncio
import os

import disnake
import yt_dlp

from app.modules.database import Database


class VoiceScripts:
    def __init__(self, logger, bot):
        self.logger = logger
        self.bot = bot
        self.db = Database()

    async def connect_to_requester_channel(self, inter: disnake.GuildCommandInteraction):
        """Подключить бота к голосовому каналу пользователя."""
        voice_state = getattr(inter.author, "voice", None)
        if not voice_state or not voice_state.channel:
            return await self._send_response(
                inter,
                "Сначала зайди в голосовой канал, чтобы я знала куда подключаться."
            )

        guild = inter.guild
        if guild is None:
            return await self._send_response(
                inter,
                "Эта команда работает только на сервере."
            )

        channel = voice_state.channel
        voice_client = guild.voice_client

        try:
            if voice_client and voice_client.channel.id == channel.id:
                return await self._send_response(
                    inter,
                    f"Я уже в {channel.mention}."
                )

            if voice_client:
                await voice_client.move_to(channel)
            else:
                await channel.connect()

            await self._send_response(
                inter,
                f"Подключилась к {channel.mention}."
            )
        except RuntimeError as runtime_error:
            await self._send_response(
                inter,
                "Для работы с голосовыми каналами нужна библиотека PyNaCl на стороне бота."
            )
            self.logger.error("Отсутствует PyNaCl для подключения к голосу: %s", runtime_error)
        except disnake.Forbidden:
            await self._send_response(
                inter,
                "У меня нет прав для подключения к этому голосовому каналу."
            )
            self.logger.warning(
                "Недостаточно прав для подключения к голосовому каналу %s (%s)",
                channel.name,
                channel.id,
            )
        except disnake.ClientException as client_error:
            await self._send_response(
                inter,
                "Сейчас не получается подключиться, попробуй ещё раз."
            )
            self.logger.error(
                "ClientException при подключении к каналу %s (%s): %s",
                channel.name,
                channel.id,
                client_error,
            )
        except Exception as error:
            await self._send_response(
                inter,
                "При подключении произошла неожиданная ошибка."
            )
            self.logger.error(
                "Неожиданная ошибка при подключении к каналу %s (%s): %s",
                channel.name if channel else "неизвестно",
                channel.id if channel else "неизвестно",
                error,
            )

    async def disconnect_with_requester(self, inter: disnake.GuildCommandInteraction):
        """Отключить бота, если пользователь находится в том же голосовом канале."""
        voice_state = getattr(inter.author, "voice", None)
        if not voice_state or not voice_state.channel:
            return await self._send_response(
                inter,
                "Сначала зайди в голосовой канал со мной, чтобы отключить бота."
            )

        guild = inter.guild
        if guild is None:
            return await self._send_response(inter, "Эта команда доступна только на сервере.")

        voice_client = guild.voice_client
        if not voice_client or not voice_client.channel:
            return await self._send_response(inter, "Я сейчас не подключена ни к одному голосовому каналу.")

        if voice_client.channel.id != voice_state.channel.id:
            return await self._send_response(
                inter,
                f"Нужно зайти в {voice_client.channel.mention}, чтобы отключить меня."
            )

        try:
            channel = voice_client.channel
            await voice_client.disconnect(force=True)
            await self._send_response(inter, f"Отключилась от {channel.mention}.")
        except disnake.ClientException as client_error:
            await self._send_response(inter, "Сейчас не получается отключиться, попробуй ещё раз.")
            self.logger.error(
                "ClientException при отключении от канала %s (%s): %s",
                voice_client.channel.name,
                voice_client.channel.id,
                client_error,
            )
        except Exception as error:
            await self._send_response(inter, "При отключении произошла неожиданная ошибка.")
            self.logger.error(
                "Неожиданная ошибка при отключении от канала %s (%s): %s",
                voice_client.channel.name if voice_client and voice_client.channel else "неизвестно",
                voice_client.channel.id if voice_client and voice_client.channel else "неизвестно",
                error,
            )

    async def play_url(self, inter: disnake.GuildCommandInteraction, url: str):
        """Добавить трек(и) в очередь и начать воспроизведение."""
        voice_state = getattr(inter.author, "voice", None)
        if not voice_state or not voice_state.channel:
            return await self._send_response(
                inter,
                "Сначала зайди в голосовой канал, чтобы я могла воспроизводить звук.",
                ephemeral=False,
            )

        guild = inter.guild
        if guild is None:
            return await self._send_response(inter, "Эта команда работает только на сервере.", ephemeral=False)

        voice_client = await self._ensure_voice_client(inter, voice_state)
        if not voice_client:
            return

        try:
            tracks = await self._extract_tracks(url)
        except Exception as error:
            self.logger.error("Ошибка при получении аудио-потока: %s", error)
            return await self._send_response(
                inter,
                "Не получилось получить аудио по этой ссылке.",
                ephemeral=False,
            )

        if not tracks:
            return await self._send_response(
                inter,
                "Не нашла треки по указанной ссылке.",
                ephemeral=False,
            )

        self.db.add_tracks_to_queue(guild.id, tracks)

        if not voice_client.is_playing() and not voice_client.is_paused():
            await self._play_next_async(guild.id)

        added_count = len(tracks)
        message = (
            f"Добавлен трек: **{tracks[0]['title']}**."
            if added_count == 1
            else f"Добавлено {added_count} треков в очередь."
        )
        await self._send_response(inter, message, ephemeral=False)

    async def pause_playback(self, inter: disnake.GuildCommandInteraction):
        """Поставить текущий трек на паузу или возобновить."""
        guild = inter.guild
        if guild is None:
            return await self._send_response(inter, "Эта команда работает только на сервере.")

        voice_client = guild.voice_client
        if not voice_client or (not voice_client.is_playing() and not voice_client.is_paused()):
            return await self._send_response(inter, "Сейчас ничего не играет.")

        if voice_client.is_paused():
            voice_client.resume()
            return await self._send_response(inter, "Возобновила воспроизведение.")

        voice_client.pause()
        await self._send_response(inter, "Поставила музыку на паузу.")

    async def stop_playback(self, inter: disnake.GuildCommandInteraction):
        """Остановить воспроизведение и очистить очередь."""
        guild = inter.guild
        if guild is None:
            return await self._send_response(inter, "Эта команда работает только на сервере.")

        voice_client = guild.voice_client
        self.db.clear_queue(guild.id)

        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()
            return await self._send_response(inter, "Остановила воспроизведение и очистила очередь.")

        return await self._send_response(inter, "Очередь очищена. Сейчас ничего не играет.")

    async def _play_next_async(self, guild_id: int):
        """Запустить следующий трек из очереди."""
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        voice_client = guild.voice_client
        if not voice_client or voice_client.is_playing() or voice_client.is_paused():
            return

        track = self.db.pop_next_track(guild_id)
        if not track:
            return

        before_opts = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        try:
            source = disnake.FFmpegPCMAudio(
                track["stream_url"],
                before_options=before_opts,
                options="-vn",
            )
            voice_client.play(
                source,
                after=lambda error: self._schedule_next(guild_id, error),
            )
            self.logger.info("Проигрываю трек: %s", track.get("title", "без названия"))
        except Exception as error:
            self.logger.error("Не удалось начать воспроизведение: %s", error)
            await self._play_next_async(guild_id)

    def _schedule_next(self, guild_id: int, error: Exception | None):
        """Запланировать проигрывание следующего трека после завершения текущего."""
        if error:
            self.logger.error("Ошибка во время воспроизведения: %s", error)
        asyncio.run_coroutine_threadsafe(self._play_next_async(guild_id), self.bot.loop)

    async def _extract_tracks(self, url: str):
        """Получить информацию о треках (одиночных или плейлист) из YouTube/ссылки."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self._extract_tracks_sync(url))

    def _extract_tracks_sync(self, url: str):
        provider_url = os.getenv("YT_POT_PROVIDER_URL", "http://127.0.0.1:4416")
        cookies_file = os.getenv("YT_COOKIES_FILE")
        opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "nocheckcertificate": True,
            "ignoreerrors": True,
            "noplaylist": False,
            "extractor_args": {
                "youtube": {
                    "player_client": ["tv_embedded"],
                    "player_skip": ["webpage"],
                    # Формат: CLIENT.CONTEXT+TOKEN_PROVIDER. Для провайдера bgutil-http используем tv_embedded.
                    "po_token": [
                        "tv_embedded.gvs+bgutilhttp;tv_embedded.player+bgutilhttp;tv_embedded.subs+bgutilhttp"
                    ],
                },
                "youtubepot-bgutilhttp": {
                    "base_url": [provider_url],
                    # Если провайдер требует, раскомментируйте строку ниже
                    # "disable_innertube": ["1"],
                },
            },
        }
        if cookies_file and os.path.exists(cookies_file):
            opts["cookiefile"] = cookies_file
        tracks = []
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            return tracks

        def add_entry(entry):
            if not entry:
                return
            stream_url = entry.get("url")
            if not stream_url and entry.get("formats"):
                for fmt in entry["formats"]:
                    stream_url = fmt.get("url")
                    if stream_url:
                        break
            title = entry.get("title") or "Трек"
            webpage = entry.get("webpage_url") or entry.get("original_url") or url
            if not stream_url:
                return
            tracks.append(
                {
                    "title": title,
                    "stream_url": stream_url,
                    "webpage_url": webpage,
                }
            )

        if "entries" in info and info.get("entries"):
            for entry in info["entries"]:
                add_entry(entry)
        else:
            add_entry(info)
        return tracks

    async def _send_response(self, inter: disnake.GuildCommandInteraction, message: str, ephemeral: bool = True):
        """Отправить ответ или follow-up в зависимости от состояния взаимодействия."""
        if inter.response.is_done():
            await inter.followup.send(message, ephemeral=ephemeral)
        else:
            await inter.response.send_message(message, ephemeral=ephemeral)

    async def _ensure_voice_client(self, inter: disnake.GuildCommandInteraction, voice_state: disnake.VoiceState):
        """Убедиться, что бот подключён к нужному голосовому каналу."""
        guild = inter.guild
        if guild is None:
            await self._send_response(inter, "Эта команда работает только на сервере.", ephemeral=False)
            return None

        voice_client = guild.voice_client
        try:
            if voice_client and voice_client.channel.id != voice_state.channel.id:
                await voice_client.move_to(voice_state.channel)
            elif not voice_client:
                voice_client = await voice_state.channel.connect()
            return voice_client
        except RuntimeError:
            await self._send_response(
                inter,
                "Для работы с голосовыми каналами нужна библиотека PyNaCl на стороне бота.",
                ephemeral=False,
            )
        except disnake.Forbidden:
            await self._send_response(
                inter,
                "У меня нет прав подключаться к этому голосовому каналу.",
                ephemeral=False,
            )
        except disnake.ClientException as client_error:
            self.logger.error("ClientException при подключении перед проигрыванием: %s", client_error)
            await self._send_response(
                inter,
                "Не удалось подключиться к голосовому каналу. Попробуй ещё раз.",
                ephemeral=False,
            )
        return None
