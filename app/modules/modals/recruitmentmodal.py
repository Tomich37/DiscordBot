import disnake
from app.modules.database import Database

class RecruitementModal(disnake.ui.Modal):
    def __init__(self, arg, guil_id, logger):
        self.logger = logger
        self.guild_id = guil_id
        self.arg = arg  # arg - это аргумент, который передается в конструкторе класса RecruitementSelect
        self.db = Database()
        components = [
            disnake.ui.TextInput(label="Немного информации", placeholder="Расскажите почему решили взять выбранную роль", custom_id="info"),
            disnake.ui.TextInput(label="Время", placeholder="Укажите сколько времени в неделю сможете уделять", custom_id="time")
        ]
        if self.arg == "Харон":
            title = "Набор на должность харона"
        elif self.arg == "Страж":
            title = "Набор на должность стража"
        else:
            title = "Набор на должность ивентмейкера"
        super().__init__(title=title, components=components, custom_id="recruitementModal")

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        try:
            info = interaction.text_values["info"]
            time = interaction.text_values["time"]
            embed = disnake.Embed(color=0x2F3136, title="Заявка отправлена!")
            embed.description = f"{interaction.author.mention}, Благодарим вас за **заявку**! " \
                                f"Если вы нам **подходите**, администрация **свяжется** с вами в ближайшее время."
            embed.set_thumbnail(url=interaction.author.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            channel_id = self.db.get_recruitment_by_guild(self.guild_id).channel_id
            channel = interaction.guild.get_channel(channel_id)  # Вставить ID канала куда будут отправляться заявки
            await channel.send(f"Заявка на должность {self.arg} {interaction.author.mention}\n\n**Краткая информация**:\n{info}\n**Готовность уделять времени**\n{time}")
        except Exception as e:
            self.logger.error(f'Ошибка в modals/recruitmentmodal: {e}')
            print(f'Ошибка в modals/recruitmentmodal: {e}')