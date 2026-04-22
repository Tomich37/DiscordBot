import asyncio
import os
import shutil
import uuid
from collections import deque
from datetime import date, timedelta
from pathlib import Path

import disnake
from moviepy import VideoFileClip, vfx

from app.modules.database import Database


class Scripts:
    MAX_CONCURRENT_CONVERSIONS = 5
    MAX_GIF_DURATION_SECONDS = 10
    GIF_FPS = 12
    GIF_MAX_WIDTH = 480

    _conversion_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CONVERSIONS)
    _queue_lock = asyncio.Lock()
    _pending_jobs = deque()

    def __init__(self, logger, bot) -> None:
        self.logger = logger
        self.bot = bot
        self.db = Database
        self._temp_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "temp"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    async def read_messages_with_reaction(self, channel_id, emoji, inter, contest_id, top_count=10):
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                self.logger.warning(f"Канал с id {channel_id} не найден.")
                return

            db = Database()
            contest_messages = db.get_contest_messages(contest_id)
            if not contest_messages:
                await channel.send("В этом конкурсе пока нет постов, привязанных к текущему запуску.")
                return

            collected_messages = []
            for contest_message in contest_messages:
                try:
                    message = await channel.fetch_message(contest_message.message_id)
                except disnake.NotFound:
                    continue

                reaction = next(
                    (item for item in message.reactions if str(item.emoji) == emoji),
                    None,
                )
                if reaction:
                    collected_messages.append(
                        {
                            "reactions_count": reaction.count,
                            "content": message.content,
                            "attachments": [attachment.url for attachment in message.attachments],
                            "url": message.jump_url,
                        }
                    )

            sorted_messages = sorted(
                collected_messages,
                key=lambda item: item["reactions_count"],
                reverse=True,
            )
            await self.send_embeds(sorted_messages, channel, top_count=top_count)
        except Exception as e:
            self.logger.error(f"Ошибка в scripts/read_messages_with_reaction: {e}")
            print(f"Ошибка в scripts/read_messages_with_reaction: {e}")

    async def send_embeds(self, sorted_messages, channel, top_count=10):
        try:
            if not sorted_messages:
                await channel.send("По этому запуску конкурса не найдено сообщений с голосами.")
                return

            for place, sorted_message in enumerate(sorted_messages[:top_count], start=1):
                embed = disnake.Embed(
                    title=f"{place} место",
                    description=sorted_message["content"] or "Без текста",
                    color=0x00FF00,
                )
                if sorted_message["attachments"]:
                    embed.set_image(url=sorted_message["attachments"][0])
                embed.add_field(
                    name="Ссылка на оригинал",
                    value=sorted_message["url"],
                    inline=False,
                )
                embed.set_footer(
                    text=f"Количество голосов {sorted_message['reactions_count']}"
                )
                await channel.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Ошибка в scripts/send_embeds: {e}")
            print(f"Ошибка в scripts/send_embeds: {e}")

    def _create_job_dir(self) -> Path:
        job_dir = self._temp_dir / f"job_{uuid.uuid4().hex}"
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def _sanitize_filename(self, filename: str) -> str:
        return Path(filename).name.replace(" ", "_")

    async def _enqueue_conversion_job(self, job_id: str) -> int:
        async with self._queue_lock:
            self._pending_jobs.append(job_id)
            return len(self._pending_jobs)

    async def _wait_for_conversion_slot(self, job_id: str) -> None:
        await self._conversion_semaphore.acquire()

        async with self._queue_lock:
            if job_id in self._pending_jobs:
                self._pending_jobs.remove(job_id)

    def _build_output_path(self, input_path: Path, output_format: str) -> Path:
        return input_path.with_suffix(".gif" if output_format == "gif" else ".mov")

    def _get_supported_suffixes(self, output_format: str) -> set[str]:
        if output_format == "gif":
            return {".mp4", ".avi", ".mkv", ".mov", ".webm"}
        return {".mp4", ".avi", ".mkv"}

    def _resize_clip(self, clip, width: int):
        if hasattr(clip, "resized"):
            return clip.resized(width=width)
        return clip.resize(width=width)

    def _speed_up_clip(self, clip, factor: float):
        if hasattr(clip, "with_speed_scaled"):
            return clip.with_speed_scaled(factor)
        return clip.fx(vfx.speedx, factor)

    def _convert_single_video(
        self,
        input_path: Path,
        output_path: Path,
        output_format: str,
    ) -> tuple[Path, float | None]:
        speed_factor = None

        with VideoFileClip(str(input_path)) as video:
            clip = video

            if output_format == "gif":
                duration = float(video.duration or 0)
                if duration > self.MAX_GIF_DURATION_SECONDS:
                    speed_factor = duration / self.MAX_GIF_DURATION_SECONDS
                    clip = self._speed_up_clip(video, speed_factor)

                if clip.w and clip.w > self.GIF_MAX_WIDTH:
                    clip = self._resize_clip(clip, self.GIF_MAX_WIDTH)

                source_fps = getattr(clip, "fps", None) or self.GIF_FPS
                clip.write_gif(
                    str(output_path),
                    fps=min(self.GIF_FPS, max(1, int(source_fps))),
                    logger=None,
                )
            else:
                clip.write_videofile(
                    str(output_path),
                    codec="libx264",
                    audio_codec="aac",
                    logger=None,
                )

        return output_path, speed_factor

    def _convert_videos_in_dir(
        self,
        video_folder: Path,
        output_format: str,
    ) -> tuple[list[Path], list[str]]:
        converted_files = []
        notices = []
        supported_suffixes = self._get_supported_suffixes(output_format)
        video_files = [
            file
            for file in video_folder.iterdir()
            if file.is_file() and file.suffix.lower() in supported_suffixes
        ]

        for input_path in video_files:
            output_path = self._build_output_path(input_path, output_format)

            try:
                converted_path, speed_factor = self._convert_single_video(
                    input_path=input_path,
                    output_path=output_path,
                    output_format=output_format,
                )

                if input_path != output_path and input_path.exists():
                    input_path.unlink()

                converted_files.append(converted_path)

                if speed_factor is not None:
                    notices.append(
                        f"`{input_path.name}` был ускорен в {speed_factor:.2f}x, "
                        f"чтобы GIF длился не дольше {self.MAX_GIF_DURATION_SECONDS} секунд."
                    )

                self.logger.info(
                    f"Успешно конвертировано: {input_path.name} -> {output_path.name}"
                )
            except Exception as clip_error:
                self.logger.error(
                    f"Ошибка при обработке файла {input_path.name}: {clip_error}"
                )

        return converted_files, notices

    async def _send_converted_files(
        self,
        inter,
        converted_files: list[Path],
        output_format: str,
        notices: list[str],
    ):
        files = [disnake.File(str(file_path)) for file_path in converted_files]
        content = (
            f"{inter.author.mention}, конвертация в `{output_format}` завершена. "
            "Готовые файлы ниже."
        )

        if notices:
            content = f"{content}\n" + "\n".join(notices)

        await inter.followup.send(content=content, files=files)

    async def process_video_conversion(
        self,
        inter,
        attachments,
        output_format: str = "mov",
    ):
        if not attachments:
            await inter.followup.send("В этом сообщении нет вложений.")
            return

        job_id = uuid.uuid4().hex
        job_dir = self._create_job_dir()
        queued_count = await self._enqueue_conversion_job(job_id)
        queue_position = None
        was_queued = queued_count > self.MAX_CONCURRENT_CONVERSIONS
        if was_queued:
            queue_position = queued_count - self.MAX_CONCURRENT_CONVERSIONS
        semaphore_acquired = False

        try:
            if was_queued:
                await inter.followup.send(
                    f"{inter.author.mention}, запрос на конвертацию в `{output_format}` поставлен в очередь. "
                    f"Позиция в очереди: {queue_position}."
                )
            else:
                await inter.followup.send(
                    f"{inter.author.mention}, запрос на конвертацию в `{output_format}` принят в обработку."
                )

            for attachment in attachments:
                safe_name = self._sanitize_filename(attachment.filename)
                await attachment.save(str(job_dir / f"downloaded_{safe_name}"))

            await self._wait_for_conversion_slot(job_id)
            semaphore_acquired = True

            if was_queued:
                position_text = (
                    f" из очереди (позиция была: {queue_position})"
                    if queue_position is not None
                    else ""
                )
                await inter.followup.send(
                    f"{inter.author.mention}, началась обработка вашей задачи{position_text}."
                )

            converted_files, notices = await asyncio.to_thread(
                self._convert_videos_in_dir,
                job_dir,
                output_format,
            )

            if not converted_files:
                await inter.followup.send(
                    f"{inter.author.mention}, не удалось сконвертировать вложения в `{output_format}`. "
                    "Поддерживаются файлы `.mp4`, `.avi`, `.mkv`, `.mov`, `.webm`."
                )
                return

            await self._send_converted_files(inter, converted_files, output_format, notices)
        except Exception as e:
            self.logger.error(f"Ошибка в scripts/process_video_conversion: {e}")
            await inter.followup.send(
                f"{inter.author.mention}, произошла ошибка при конвертации: {e}"
            )
        finally:
            async with self._queue_lock:
                if job_id in self._pending_jobs:
                    self._pending_jobs.remove(job_id)

            if semaphore_acquired:
                self._conversion_semaphore.release()

            shutil.rmtree(job_dir, ignore_errors=True)

    async def send_daily_statistics(self):
        try:
            yesterday = date.today() - timedelta(days=1)
            active_channels = self.db.get_all_statistics_channel()

            for channel_id in active_channels:
                stats = self.db.get_yesterday_statistic(
                    channel_id=channel_id,
                    date=yesterday,
                )
                if stats:
                    channel_obj = self.bot.get_channel(channel_id)
                    if channel_obj:
                        await channel_obj.send(
                            f"Статистика за {yesterday}: {stats.message_count} сообщений"
                        )
        except Exception as e:
            self.logger.error(f"Ошибка в scripts/send_daily_statistics: {e}")
            print(f"Ошибка в scripts/send_daily_statistics: {e}")
