import disnake
from app.modules.database import Database


class RecruitementModal(disnake.ui.Modal):
    def __init__(self, arg, guild_id, logger):
        self.logger = logger
        self.guild_id = guild_id
        self.arg = arg  # arg - это аргумент, который передается в конструкторе класса RecruitementSelect
        self.db = Database()
        questions = self.db.get_recruitment_questions(guild_id)

        if not questions:
            questions = [
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

        self.question_labels = []
        components = []
        for index, question in enumerate(questions[:5]):
            label = question["label"] if isinstance(question, dict) else question.label
            placeholder = question["placeholder"] if isinstance(question, dict) else question.placeholder
            style = question["style"] if isinstance(question, dict) else question.style
            self.question_labels.append(label)
            text_style = (
                disnake.TextInputStyle.short
                if style == "short"
                else disnake.TextInputStyle.paragraph
            )
            components.append(
                disnake.ui.TextInput(
                    label=label[:45],
                    placeholder=placeholder[:100],
                    custom_id=f"question_{index}",
                    style=text_style,
                    max_length=1000,
                )
            )

        super().__init__(
            title=f"Заявка: {self.arg}"[:45],
            components=components,
            custom_id="recruitementModal",
        )

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        try:
            recruitment = self.db.get_recruitment_by_guild(interaction.guild.id)
            if not recruitment or not recruitment.channel_id:
                await interaction.response.send_message(
                    "Канал для заявок ещё не настроен. Обратитесь к администрации.",
                    ephemeral=True,
                )
                return

            channel = interaction.guild.get_channel(recruitment.channel_id)
            if not channel:
                await interaction.response.send_message(
                    "Не удалось найти канал для заявок. Попросите администрацию перенастроить систему.",
                    ephemeral=True,
                )
                return

            embed = disnake.Embed(color=0x2F3136, title="Заявка отправлена!")
            embed.description = f"{interaction.author.mention}, Благодарим вас за **заявку**! " \
                                f"Если вы нам **подходите**, администрация **свяжется** с вами в ближайшее время."
            embed.set_thumbnail(url=interaction.author.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)

            # Отдельный embed удобнее читать модераторам и проще дополнять статусами.
            request_embed = disnake.Embed(
                title=f"Новая заявка: {self.arg}",
                color=0xF1C40F,
            )
            request_embed.add_field(
                name="Кандидат",
                value=f"{interaction.author.mention}\nID: `{interaction.author.id}`",
                inline=False,
            )

            for index, value in enumerate(interaction.text_values.values()):
                if index < len(self.question_labels):
                    field_name = self.question_labels[index]
                else:
                    field_name = f"Ответ {index + 1}"

                request_embed.add_field(
                    name=field_name[:256],
                    value=value[:1024] or "Не указано",
                    inline=False,
                )

            request_embed.set_thumbnail(url=interaction.author.display_avatar.url)
            request_embed.set_footer(text="Заявка ожидает рассмотрения администрацией")
            await channel.send(embed=request_embed)
        except Exception as e:
            self.logger.error(f'Ошибка в modals/recruitmentmodal: {e}')
            print(f'Ошибка в modals/recruitmentmodal: {e}')
