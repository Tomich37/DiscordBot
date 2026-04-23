import disnake

from app.modules.database import Database
from app.modules.menus.recruitment import RecruitmentView


DEFAULT_RECRUITMENT_QUESTIONS = [
    {
        "label": "Немного информации",
        "placeholder": "Расскажите, почему хотите занять эту должность",
        "style": "paragraph",
    },
    {
        "label": "Время",
        "placeholder": "Сколько времени в неделю сможете уделять?",
        "style": "short",
    },
]


class RecruitmentSetupModal(disnake.ui.Modal):
    def __init__(
        self,
        logger,
        requests_channel_id: int,
        panel_channel_id: int,
        position_count: int,
    ):
        self.logger = logger
        self.requests_channel_id = requests_channel_id
        self.panel_channel_id = panel_channel_id
        self.position_count = position_count
        self.db = Database()

        components = [
            disnake.ui.TextInput(
                label=f"Роль {index + 1}",
                placeholder="Например: Модератор | Следит за порядком",
                custom_id=f"position_{index}",
                max_length=200,
            )
            for index in range(position_count)
        ]

        super().__init__(
            title="Настройка набора",
            components=components,
            custom_id="recruitment_setup_modal",
        )

    @staticmethod
    def _parse_position(raw_value: str, index: int) -> dict:
        parts = [part.strip() for part in raw_value.split("|", maxsplit=1)]
        title = parts[0] if parts and parts[0] else f"Должность {index + 1}"
        description = parts[1] if len(parts) > 1 and parts[1] else "Без описания"

        return {
            "title": title[:100],
            "description": description[:100],
        }

    def _collect_positions(self, text_values: dict[str, str]) -> list[dict]:
        positions = []
        for index in range(self.position_count):
            raw_value = text_values.get(f"position_{index}", "")
            positions.append(self._parse_position(raw_value, index))

        return positions

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        try:
            positions = self._collect_positions(interaction.text_values)

            panel_channel = interaction.guild.get_channel(self.panel_channel_id)
            requests_channel = interaction.guild.get_channel(self.requests_channel_id)
            if not panel_channel or not requests_channel:
                await interaction.response.send_message(
                    "Не удалось найти один из каналов. Запустите настройку заново.",
                    ephemeral=True,
                )
                return

            self.db.create_update_recruitment_channel(
                guild_id=interaction.guild.id,
                channel_id=requests_channel.id,
            )
            self.db.replace_recruitment_positions(interaction.guild.id, positions)

            # Если вопросы ещё не настроены, оставляем рабочий базовый шаблон анкеты.
            if not self.db.get_recruitment_questions(interaction.guild.id):
                self.db.replace_recruitment_questions(
                    interaction.guild.id,
                    DEFAULT_RECRUITMENT_QUESTIONS,
                )

            embed = disnake.Embed(
                title="Набор в команду сервера",
                description=(
                    "Выберите направление в меню ниже и заполните короткую анкету. "
                    "После отправки заявка попадёт администрации на рассмотрение."
                ),
                color=0x2F3136,
            )
            embed.add_field(
                name="Доступные направления",
                value="\n".join(
                    f"**{position['title']}** - {position['description']}"
                    for position in positions
                )[:1024],
                inline=False,
            )
            embed.set_footer(text="Заявку можно отправить через выпадающее меню")

            panel_message = await panel_channel.send(
                embed=embed,
                view=RecruitmentView(self.logger, positions),
            )
            self.db.create_update_recruitment_message(
                guild_id=interaction.guild.id,
                message_id=panel_message.id,
            )

            await interaction.response.send_message(
                f"Панель набора создана в канале {panel_channel.mention}.\n"
                f"Заявки будут приходить в канал {requests_channel.mention}.",
                ephemeral=True,
            )
        except Exception as e:
            self.logger.error(f"Ошибка в modals/recruitment_setup_modal: {e}")
            print(f"Ошибка в modals/recruitment_setup_modal: {e}")
