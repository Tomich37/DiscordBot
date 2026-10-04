import disnake
from disnake.interactions import MessageInteraction
from app.modules.modals.recruitmentmodal import RecruitementModal


# Меню для выбора должности в заявке.
class RecruitmentSelect(disnake.ui.StringSelect):
    def __init__(self, db, logger, positions: list[dict] | None = None):
        self.db = db
        self.logger = logger
        positions = positions or [
            {
                "title": "Заявка",
                "description": "Выберите этот пункт, если панель была создана до обновления",
            }
        ]
        options = [
            disnake.SelectOption(
                label=position["title"][:100],
                value=position["title"][:100],
                description=position["description"][:100],
            )
            for position in positions[:25]
        ]
        super().__init__(
            placeholder="Выбери желаемую должность",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="recruitment_select",
        )
        
    async def callback(self, interaction: MessageInteraction):
        try:
            questions = await self.db.get_recruitment_questions(interaction.guild.id)
            await interaction.response.send_modal(
                RecruitementModal(
                    self.db,
                    interaction.values[0],
                    interaction.guild.id,
                    self.logger,
                    questions,
                )
            )
        except Exception as e:
            self.logger.exception(f"Ошибка в menus/recruitment: {e}")
            print(f"Ошибка в menus/recruitment: {e}")


class RecruitmentView(disnake.ui.View):
    def __init__(self, db, logger, positions: list[dict] | None = None):
        super().__init__(timeout=None)
        self.add_item(RecruitmentSelect(db, logger, positions))

