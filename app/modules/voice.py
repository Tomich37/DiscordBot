import disnake


class VoiceScripts:
    def __init__(self, logger, bot):
        self.logger = logger
        self.bot = bot

    async def connect_to_requester_channel(self, inter: disnake.GuildCommandInteraction):
        """Connect the bot to the same voice channel as the interaction author."""
        voice_state = getattr(inter.author, "voice", None)
        if not voice_state or not voice_state.channel:
            return await self._send_response(
                inter,
                "Join a voice channel first so I know where to connect."
            )

        channel = voice_state.channel
        guild = inter.guild
        if guild is None:
            return await self._send_response(
                inter,
                "This command only works inside a server."
            )

        voice_client = guild.voice_client

        try:
            if voice_client and voice_client.channel.id == channel.id:
                return await self._send_response(
                    inter,
                    f"I'm already in {channel.mention}."
                )

            if voice_client:
                await voice_client.move_to(channel)
            else:
                await channel.connect()

            await self._send_response(
                inter,
                f"Connected to {channel.mention}."
            )
        except RuntimeError as runtime_error:
            await self._send_response(
                inter,
                "Voice support requires the PyNaCl package on the bot host."
            )
            self.logger.error("PyNaCl missing for voice connection: %s", runtime_error)
        except disnake.Forbidden:
            await self._send_response(
                inter,
                "I don't have permission to connect to that voice channel."
            )
            self.logger.warning(
                "Missing permission to connect to voice channel %s (%s)",
                channel.name,
                channel.id,
            )
        except disnake.ClientException as client_error:
            await self._send_response(
                inter,
                "I couldn't connect right now, please try again."
            )
            self.logger.error(
                "ClientException while joining channel %s (%s): %s",
                channel.name,
                channel.id,
                client_error,
            )
        except Exception as error:
            await self._send_response(
                inter,
                "Something unexpected happened while connecting."
            )
            self.logger.error(
                "Unexpected error while joining channel %s (%s): %s",
                channel.name if channel else "unknown",
                channel.id if channel else "unknown",
                error,
            )

    async def disconnect_with_requester(self, inter: disnake.GuildCommandInteraction):
        """Disconnect the bot if the requester shares the current voice channel."""
        voice_state = getattr(inter.author, "voice", None)
        if not voice_state or not voice_state.channel:
            return await self._send_response(
                inter,
                "Join the voice channel with me first to disconnect the bot."
            )

        guild = inter.guild
        if guild is None:
            return await self._send_response(inter, "This command is only available inside a server.")

        voice_client = guild.voice_client
        if not voice_client or not voice_client.channel:
            return await self._send_response(inter, "I'm not connected to any voice channel right now.")

        if voice_client.channel.id != voice_state.channel.id:
            return await self._send_response(
                inter,
                f"You need to be in {voice_client.channel.mention} to disconnect me."
            )

        try:
            channel = voice_client.channel
            await voice_client.disconnect(force=True)
            await self._send_response(inter, f"Disconnected from {channel.mention}.")
        except disnake.ClientException as client_error:
            await self._send_response(inter, "I couldn't disconnect right now, please try again.")
            self.logger.error(
                "ClientException while disconnecting from channel %s (%s): %s",
                voice_client.channel.name,
                voice_client.channel.id,
                client_error,
            )
        except Exception as error:
            await self._send_response(inter, "Something unexpected happened while disconnecting.")
            self.logger.error(
                "Unexpected error while disconnecting from channel %s (%s): %s",
                voice_client.channel.name if voice_client and voice_client.channel else "unknown",
                voice_client.channel.id if voice_client and voice_client.channel else "unknown",
                error,
            )

    async def _send_response(self, inter: disnake.GuildCommandInteraction, message: str):
        """Send a response or followup depending on whether the interaction has been answered."""
        if inter.response.is_done():
            await inter.followup.send(message, ephemeral=True)
        else:
            await inter.response.send_message(message, ephemeral=True)
