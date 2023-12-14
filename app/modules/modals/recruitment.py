import disnake
from disnake.ext import commands
from disnake.interactions import MessageInteraction
from disnake import TextInputStyle

# Меню для выбора роли
class RecruitmentSelect(disnake.ui.StringSelect):
    def __init__(self):
        options = [
            disnake.SelectOption(label='Харон', value='Харон', description='Роль для собеседований и принятия на сервер'),
            disnake.SelectOption(label='Страж', value='Страж', description='Роль модератора'),
            disnake.SelectOption(label='Ивентмейкер', value='Ивентмейкер', description='Роль для проведения ивентов'),
        ]
        super().__init__(
            placeholder="Выбери желаемую роль", options=options, min_values=0, max_values=1, custom_id='recuitment'
            )
        
    async def callback(self, interaction: MessageInteraction):
        if not interaction.values:
            await interaction.response.defer()
        else:
            await interaction.response.send_message(
                f"Вы выбрали {interaction.values[0]}", ephemeral=True
            )