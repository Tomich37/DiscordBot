import asyncio
from io import BytesIO
from pathlib import Path

import disnake

from app.modules.database import Database


ANONYMOUS_IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
ANONYMOUS_DOCUMENT_EXTENSIONS = {".pdf", ".txt"}
ANONYMOUS_FILE_EXTENSIONS = (
    ANONYMOUS_IMAGE_EXTENSIONS | ANONYMOUS_DOCUMENT_EXTENSIONS
)
ANONYMOUS_MAX_FILES = 4
ANONYMOUS_MODAL_TIMEOUT_SECONDS = 30 * 60
ANONYMOUS_INTERACTION_ACK_TIMEOUT_SECONDS = 2.5


class AnonymousMessageModal(disnake.ui.Modal):
    def __init__(
        self,
        db: Database,
        logger,
        channel_id: int,
        author_id: int,
        interaction_id: int,
    ) -> None:
        self.db = db
        self.logger = logger
        self.channel_id = channel_id
        self.author_id = author_id
        self._submission_lock = asyncio.Lock()
        self._published = False

        components = [
            disnake.ui.Label(
                "Анонимное сообщение",
                disnake.ui.TextInput(
                    custom_id="message",
                    style=disnake.TextInputStyle.paragraph,
                    placeholder="Введите текст сообщения",
                    min_length=1,
                    max_length=4000,
                ),
                description="Автор сообщения не будет указан в публикации.",
            ),
            disnake.ui.Label(
                "Вложения",
                disnake.ui.FileUpload(
                    custom_id="files",
                    min_values=0,
                    max_values=ANONYMOUS_MAX_FILES,
                    required=False,
                ),
                description="До 4 файлов: PNG, JPG, GIF, WEBP, PDF или TXT.",
            ),
        ]

        super().__init__(
            title="Анонимное сообщение",
            components=components,
            custom_id=f"anonymous_message:{interaction_id}",
            timeout=ANONYMOUS_MODAL_TIMEOUT_SECONDS,
        )

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        if self._submission_lock.locked() or self._published:
            await self._show_duplicate_notice(interaction)
            return

        async with self._submission_lock:
            await self._process_submission(interaction)

    async def _process_submission(
        self,
        interaction: disnake.ModalInteraction,
    ) -> None:
        interaction_acknowledged = False
        try:
            # При временном сбое Discord продолжаем публикацию обычным сообщением.
            try:
                await asyncio.wait_for(
                    interaction.response.defer(ephemeral=True),
                    timeout=ANONYMOUS_INTERACTION_ACK_TIMEOUT_SECONDS,
                )
                interaction_acknowledged = True
            except (
                TimeoutError,
                disnake.NotFound,
                disnake.InteractionTimedOut,
            ) as error:
                self.logger.warning(
                    "Discord не подтвердил форму /anonimuska, "
                    f"отправка продолжена без interaction-ответа: {error}"
                )

            if interaction.author.id != self.author_id:
                await self._edit_response(
                    interaction,
                    "Эта форма была открыта другим пользователем.",
                    interaction_acknowledged,
                )
                return

            message = interaction.text_values.get("message", "").strip()
            if not message:
                await self._edit_response(
                    interaction,
                    "Анонимное сообщение не может быть пустым.",
                    interaction_acknowledged,
                )
                return

            anonymous_channels = await asyncio.to_thread(
                self.db.get_all_anonimus_channel
            )
            if self.channel_id not in anonymous_channels:
                await self._edit_response(
                    interaction,
                    "Данный канал не поддерживает анонимные сообщения.",
                    interaction_acknowledged,
                )
                return

            target_channel = interaction.guild.get_channel(self.channel_id)
            if target_channel is None:
                await self._edit_response(
                    interaction,
                    "Не удалось найти канал для отправки сообщения.",
                    interaction_acknowledged,
                )
                return

            attachments = list(interaction.resolved_values.get("files", ()))
            invalid_files = [
                attachment.filename
                for attachment in attachments
                if self._get_extension(attachment.filename)
                not in ANONYMOUS_FILE_EXTENSIONS
            ]
            if invalid_files:
                await self._edit_response(
                    interaction,
                    "Поддерживаются файлы в форматах PNG, JPG, GIF, WEBP, PDF и TXT.",
                    interaction_acknowledged,
                )
                return

            oversized_files = [
                attachment.filename
                for attachment in attachments
                if attachment.size > interaction.guild.filesize_limit
            ]
            if oversized_files:
                size_limit_mb = interaction.guild.filesize_limit // (1024 * 1024)
                await self._edit_response(
                    interaction,
                    f"Размер каждого файла не должен превышать {size_limit_mb} МБ.",
                    interaction_acknowledged,
                )
                return

            files, first_image_name = await self._prepare_files(attachments)
            embed = self._build_embed(message, first_image_name)

            send_options = {"embed": embed}
            if files:
                send_options["files"] = files
            await target_channel.send(**send_options)
            self._published = True

            if interaction_acknowledged:
                try:
                    await interaction.delete_original_response()
                except (disnake.NotFound, disnake.InteractionTimedOut):
                    self.logger.warning(
                        "Анонимное сообщение отправлено, но служебный ответ "
                        "формы уже истёк"
                    )

            self.logger.info(
                f"Анонимное сообщение от {interaction.author} "
                f"(ID: {interaction.author.id}) в канале {target_channel} "
                f"(ID: {self.channel_id}), вложений: {len(attachments)}: {message[:100]}"
            )
        except Exception as error:
            self.logger.exception(
                f"Ошибка в modals/anonymous_message_modal: {error}"
            )
            print(f"Ошибка при отправке анонимного сообщения: {error}")
            await self._show_error(interaction, interaction_acknowledged)

    @staticmethod
    def _get_extension(filename: str) -> str:
        return Path(filename).suffix.lower()

    async def _prepare_files(
        self,
        attachments: list[disnake.Attachment],
    ) -> tuple[list[disnake.File], str | None]:
        files = []
        first_image_name = None
        image_number = 0
        document_number = 0

        for attachment in attachments:
            extension = self._get_extension(attachment.filename)
            if extension in ANONYMOUS_IMAGE_EXTENSIONS:
                image_number += 1
                filename = f"anonymous_image_{image_number}{extension}"
                if first_image_name is None:
                    first_image_name = filename
            else:
                document_number += 1
                filename = f"anonymous_file_{document_number}{extension}"

            file_bytes = await attachment.read(use_cached=True)
            files.append(disnake.File(BytesIO(file_bytes), filename=filename))

        return files, first_image_name

    @staticmethod
    def _build_embed(message: str, first_image_name: str | None) -> disnake.Embed:
        embed = disnake.Embed(
            title="Анонимуська",
            description=message,
            color=0x00008B,
        )
        embed.set_author(
            name="Emiliabot",
            url=(
                "https://discord.com/api/oauth2/authorize"
                "?client_id=602393416017379328&permissions=8"
                "&scope=bot+applications.commands"
            ),
            icon_url=(
                "https://media.discordapp.net/attachments/1186903406196047954/"
                "1186903657904623637/avatar_2.png"
            ),
        )
        embed.set_footer(text="Made by the_usual_god")
        if first_image_name is not None:
            embed.set_image(url=f"attachment://{first_image_name}")

        return embed

    async def _edit_response(
        self,
        interaction: disnake.ModalInteraction,
        message: str,
        interaction_acknowledged: bool,
    ) -> None:
        if not interaction_acknowledged:
            self.logger.warning(
                "Не удалось показать ответ /anonimuska: взаимодействие уже истекло"
            )
            return

        await interaction.edit_original_response(content=message)

    async def _show_duplicate_notice(
        self,
        interaction: disnake.ModalInteraction,
    ) -> None:
        message = (
            "Анонимное сообщение уже отправлено."
            if self._published
            else "Анонимное сообщение уже отправляется."
        )
        try:
            await interaction.response.send_message(message, ephemeral=True)
        except (disnake.NotFound, disnake.InteractionTimedOut):
            self.logger.warning(
                "Не удалось показать статус повторной отправки /anonimuska"
            )

    async def _show_error(
        self,
        interaction: disnake.ModalInteraction,
        interaction_acknowledged: bool,
    ) -> None:
        error_message = (
            "Не удалось отправить анонимное сообщение. Попробуйте ещё раз позже."
        )
        try:
            if interaction_acknowledged:
                await interaction.edit_original_response(content=error_message)
            else:
                self.logger.warning(
                    "Не удалось показать ошибку /anonimuska: "
                    "взаимодействие уже истекло"
                )
        except (disnake.NotFound, disnake.InteractionTimedOut):
            self.logger.warning(
                "Не удалось показать ошибку /anonimuska: взаимодействие уже истекло"
            )
