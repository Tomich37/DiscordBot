import disnake


class VoiceScripts:
    def __init__(self, logger, bot):
        self.logger = logger
        self.bot = bot

    async def connect_to_requester_channel(self, inter: disnake.GuildCommandInteraction):
        """Подключить бота к голосовому каналу пользователя."""
        voice_state = getattr(inter.author, "voice", None)
        if not voice_state or not voice_state.channel:
            return await self._send_response(
                inter,
                "Сначала зайди в голосовой канал, чтобы я знала куда подключаться."
            )

        channel = voice_state.channel
        guild = inter.guild
        if guild is None:
            return await self._send_response(
                inter,
                "Эта команда работает только на сервере."
            )

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

    async def _send_response(self, inter: disnake.GuildCommandInteraction, message: str):
        """Отправить ответ или follow-up в зависимости от состояния взаимодействия."""
        if inter.response.is_done():
            await inter.followup.send(message, ephemeral=True)
        else:
            await inter.response.send_message(message, ephemeral=True)
