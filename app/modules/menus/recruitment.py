import disnake
from disnake.interactions import MessageInteraction
from app.modules.modals.recruitmentmodal import RecruitementModal
from app.modules.database import Database

# Меню для выбора роли
class RecruitmentSelect(disnake.ui.StringSelect):
    def __init__(self, logger, guild_id):
        self.logger = logger
        self.guild_id = guild_id
        self.db = Database()
        options = [
            disnake.SelectOption(label='Харон', value='Харон', description='Роль для собеседований и принятия на сервер'),
            disnake.SelectOption(label='Страж', value='Страж', description='Роль модератора'),
            disnake.SelectOption(label='Ивентмейкер', value='Ивентмейкер', description='Роль для проведения ивентов'),
        ]
        super().__init__(
            placeholder="Выбери желаемую роль", options=options, min_values=0, max_values=1, custom_id='recuitment'
            )
        
    async def callback(self, interaction: MessageInteraction):
        try:
            if not interaction.values:
                await interaction.response.defer()
            else:
                response_message = await interaction.response.send_message(
                    await interaction.response.send_modal(RecruitementModal(interaction.values[0], self.guild_id, self.logger))
                )
                message_id = response_message.id
                self.db.create_update_recruitment_message(message_id)
        except Exception as e:
            self.logger.error(f'Ошибка в menus/recruitment: {e}')
            print(f'Ошибка в menus/recruitment: {e}')

