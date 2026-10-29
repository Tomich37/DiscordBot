from datetime import datetime, timedelta, timezone

import disnake
from disnake.ext import commands, tasks

from app.modules.interaction_response import send_interaction_response


SPORT_COLOR = 0x2ECC71
FINAL_SPORT_COLOR = 0xF1C40F


def _discord_datetime(value: datetime) -> datetime:
    """Помечает сохранённое UTC-время часовым поясом для Discord."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _progress_bar(current: int, target: int, width: int = 12) -> str:
    """Строит компактную шкалу общего прогресса."""

    ratio = min(max(current / target, 0), 1) if target > 0 else 0
    filled = round(ratio * width)
    return "█" * filled + "░" * (width - filled)


def _leaderboard_text(rows: list[dict], unit_name: str) -> str:
    if not rows:
        return "Пока никто не записался."

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    return "\n".join(
        f"{medals.get(place, f'**{place}.**')} <@{row['user_id']}> — "
        f"**{row['total_amount']:,}** {unit_name}"
        for place, row in enumerate(rows, start=1)
    )


class SportCommands(commands.Cog):
    """Команды совместных спортивных челленджей."""

    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db = bot.async_db
        self.check_sport_deadlines.start()

    def cog_unload(self):
        self.check_sport_deadlines.cancel()

    @commands.slash_command(
        name="sport",
        description="Совместные спортивные челленджи сервера",
        dm_permission=False,
    )
    async def sport(self, inter: disnake.GuildCommandInteraction):
        pass

    @sport.sub_command(
        name="create",
        description="Создать новый спортивный челлендж",
    )
    @commands.has_permissions(manage_guild=True)
    async def sport_create(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: disnake.TextChannel,
        name: str,
        unit: str,
        target: int,
        duration_days: int,
    ):
        """
        Создаёт общую цель и закрепляет её за выбранным каналом.

        Parameters
        ----------
        channel: Канал для спортивного челленджа
        name: Название челленджа, например «100 000 шагов — ноябрь»
        unit: Единица результата, например «шагов»
        target: Общая цель для всех участников
        duration_days: Продолжительность в днях
        """

        name = name.strip()
        unit = unit.strip()
        if not name or len(name) > 100:
            await send_interaction_response(
                inter,
                "Название челленджа должно содержать от 1 до 100 символов.",
                ephemeral=True,
            )
            return
        if not unit or len(unit) > 30:
            await send_interaction_response(
                inter,
                "Название единицы должно содержать от 1 до 30 символов.",
                ephemeral=True,
            )
            return
        if target <= 0 or target > 9_000_000_000_000_000_000:
            await send_interaction_response(inter, "Цель должна быть положительным числом.", ephemeral=True)
            return
        if duration_days < 1 or duration_days > 365:
            await send_interaction_response(
                inter,
                "Продолжительность должна быть от 1 до 365 дней.",
                ephemeral=True,
            )
            return

        ends_at = datetime.utcnow() + timedelta(days=duration_days)
        result = await self.db.create_sport_challenge(
            guild_id=inter.guild.id,
            channel_id=channel.id,
            creator_id=inter.author.id,
            activity_name=name,
            unit_name=unit,
            target_amount=target,
            ends_at=ends_at,
        )
        if result["status"] == "already_active":
            active = result["challenge"]
            await send_interaction_response(
                inter,
                f"В {channel.mention} уже есть активный челлендж с названием "
                f"**{active['activity_name']}**.",
                ephemeral=True,
            )
            return

        challenge = result["challenge"]
        embed = self._build_status_embed(challenge)
        embed.description = (
            f"Записывайтесь через `/sport join challenge:{name}`, затем добавляйте результат "
            f"командой `/sport add challenge:{name}`. Общая цель складывается из результатов всех участников."
        )
        try:
            await channel.send(embed=embed)
        except disnake.HTTPException:
            await self.db.finish_sport_challenge(challenge["id"], reason="publish_failed")
            await self.db.mark_sport_result_announced(challenge["id"])
            self.logger.exception("Не удалось опубликовать новый спортивный челлендж")
            await send_interaction_response(
                inter,
                "Не удалось опубликовать челлендж. Проверьте права бота в выбранном канале.",
                ephemeral=True,
            )
            return

        await send_interaction_response(
            inter,
            f"Челлендж **{name}** создан в {channel.mention}.",
            ephemeral=True,
        )

    @sport.sub_command(name="join", description="Записаться в спортивный челлендж по названию")
    async def sport_join(self, inter: disnake.GuildCommandInteraction, challenge: str):
        """
        Записывает участника в выбранный челлендж.

        Parameters
        ----------
        challenge: Название челленджа
        """

        selected = await self._challenge_in_current_channel(inter, challenge)
        if not selected:
            return

        status = await self.db.join_sport_challenge(selected["id"], inter.author.id)
        messages = {
            "joined": f"Вы записались в челлендж **{selected['activity_name']}**!",
            "already_joined": "Вы уже участвуете в этом челлендже.",
            "inactive": "Челлендж уже завершён.",
            "expired": "Срок челленджа уже закончился. Итоговый рейтинг скоро появится в канале.",
        }
        await send_interaction_response(inter, messages[status], ephemeral=True)

    @sport.sub_command(name="add", description="Добавить результат в челлендж по названию")
    async def sport_add(
        self,
        inter: disnake.GuildCommandInteraction,
        challenge: str,
        amount: int,
    ):
        """
        Добавляет новую отметку участника.

        Parameters
        ----------
        challenge: Название челленджа
        amount: Сколько выполнено с прошлой отметки
        """

        if amount <= 0 or amount > 9_000_000_000_000_000_000:
            await send_interaction_response(inter, "Результат должен быть положительным числом.", ephemeral=True)
            return

        selected = await self._challenge_in_current_channel(inter, challenge)
        if not selected:
            return

        result = await self.db.add_sport_progress(selected["id"], inter.author.id, amount)
        if result["status"] == "not_joined":
            await send_interaction_response(
                inter,
                f"Сначала запишитесь командой `/sport join challenge:{selected['activity_name']}`.",
                ephemeral=True,
            )
            return
        if result["status"] in {"inactive", "expired"}:
            await send_interaction_response(inter, "Челлендж уже завершён.", ephemeral=True)
            await self._publish_pending_results()
            return

        updated = result["challenge"]
        await send_interaction_response(
            inter,
            f"В **{updated['activity_name']}** добавлено **{amount:,} {updated['unit_name']}**. "
            f"Общий прогресс: **{result['total_amount']:,} / {updated['target_amount']:,}**.",
            ephemeral=True,
        )
        if result["status"] == "completed":
            await self._publish_final_results(updated)

    @sport.sub_command(name="status", description="Показать прогресс челленджа по названию")
    async def sport_status(self, inter: disnake.GuildCommandInteraction, challenge: str):
        selected = await self._challenge_in_current_channel(inter, challenge)
        if selected:
            await send_interaction_response(inter, embed=self._build_status_embed(selected))

    @sport.sub_command(name="top", description="Показать рейтинг челленджа по названию")
    async def sport_top(self, inter: disnake.GuildCommandInteraction, challenge: str):
        selected = await self._challenge_in_current_channel(
            inter,
            challenge,
            active_only=False,
        )
        if not selected:
            return

        rows = await self.db.get_sport_leaderboard(selected["id"])
        await send_interaction_response(inter, embed=self._build_leaderboard_embed(selected, rows))

    @sport.sub_command(name="finish", description="Досрочно завершить челлендж по названию")
    @commands.has_permissions(manage_guild=True)
    async def sport_finish(self, inter: disnake.GuildCommandInteraction, challenge: str):
        selected = await self._challenge_in_current_channel(inter, challenge)
        if not selected:
            return

        selected = await self.db.finish_sport_challenge(selected["id"], reason="manual")
        published = await self._publish_final_results(selected)
        message = f"Челлендж **{selected['activity_name']}** завершён, итоговый рейтинг опубликован."
        if not published:
            message = (
                f"Челлендж **{selected['activity_name']}** завершён, но рейтинг пока не удалось "
                "опубликовать. Бот повторит попытку."
            )
        await send_interaction_response(inter, message, ephemeral=True)

    async def _challenge_in_current_channel(
        self,
        inter,
        challenge_name: str,
        active_only: bool = True,
    ):
        challenge = await self.db.get_sport_challenge_by_name(
            guild_id=inter.guild.id,
            channel_id=inter.channel.id,
            activity_name=challenge_name,
            active_only=active_only,
        )
        if not challenge:
            await send_interaction_response(
                inter,
                f"{'Активный челлендж' if active_only else 'Челлендж'} "
                f"**{challenge_name.strip()}** в этом канале не найден.",
                ephemeral=True,
            )
            return None
        return challenge

    async def _challenge_name_choices(
        self,
        inter: disnake.ApplicationCommandInteraction,
        current: str,
        active_only: bool,
    ) -> dict[str, str]:
        if not inter.guild or not inter.channel:
            return {}

        names = await self.db.get_sport_challenge_names(
            guild_id=inter.guild.id,
            channel_id=inter.channel.id,
            search=current,
            active_only=active_only,
        )
        return {name: name for name in names}

    @sport_join.autocomplete("challenge")
    @sport_add.autocomplete("challenge")
    @sport_status.autocomplete("challenge")
    @sport_finish.autocomplete("challenge")
    async def autocomplete_active_challenge(
        self,
        inter: disnake.ApplicationCommandInteraction,
        current: str,
    ):
        """Подсказывает активные челленджи текущего канала."""

        return await self._challenge_name_choices(inter, current, active_only=True)

    @sport_top.autocomplete("challenge")
    async def autocomplete_any_challenge(
        self,
        inter: disnake.ApplicationCommandInteraction,
        current: str,
    ):
        """Подсказывает активные и завершённые челленджи текущего канала."""

        return await self._challenge_name_choices(inter, current, active_only=False)

    @staticmethod
    def _build_status_embed(challenge: dict) -> disnake.Embed:
        current = challenge.get("total_amount", 0)
        target = challenge["target_amount"]
        percent = min(current / target * 100, 100) if target else 0
        embed = disnake.Embed(
            title=f"🏃 {challenge['activity_name']}",
            color=SPORT_COLOR,
        )
        embed.add_field(
            name="Общий прогресс",
            value=(
                f"`{_progress_bar(current, target)}` **{percent:.1f}%**\n"
                f"**{current:,} / {target:,}** {challenge['unit_name']}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Завершение",
            value=disnake.utils.format_dt(_discord_datetime(challenge["ends_at"]), style="R"),
            inline=True,
        )
        embed.add_field(name="Спортивный канал", value=f"<#{challenge['channel_id']}>", inline=True)
        return embed

    @staticmethod
    def _build_leaderboard_embed(challenge: dict, rows: list[dict], final: bool = False) -> disnake.Embed:
        title = "🏆 Итоги спортивного челленджа" if final else "🏅 Спортивный рейтинг"
        embed = disnake.Embed(
            title=title,
            description=f"**{challenge['activity_name']}**\n{_leaderboard_text(rows, challenge['unit_name'])}",
            color=FINAL_SPORT_COLOR if final else SPORT_COLOR,
        )
        embed.add_field(
            name="Общий результат",
            value=f"**{challenge.get('total_amount', 0):,} / {challenge['target_amount']:,}** {challenge['unit_name']}",
            inline=False,
        )
        if final:
            reasons = {
                "target_reached": "Общая цель достигнута",
                "time_expired": "Заданный период завершён",
                "manual": "Досрочно завершено модератором",
                "publish_failed": "Создание отменено",
            }
            embed.set_footer(text=reasons.get(challenge.get("finish_reason"), "Челлендж завершён"))
        return embed

    async def _publish_final_results(self, challenge: dict) -> bool:
        if challenge.get("result_announced"):
            return True

        channel = self.bot.get_channel(challenge["channel_id"])
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(challenge["channel_id"])
            except (disnake.NotFound, disnake.Forbidden, disnake.HTTPException):
                self.logger.exception(
                    "Не удалось найти спортивный канал %s для челленджа %s",
                    challenge["channel_id"],
                    challenge["id"],
                )
                return False

        rows = await self.db.get_sport_leaderboard(challenge["id"])
        try:
            await channel.send(embed=self._build_leaderboard_embed(challenge, rows, final=True))
        except (disnake.Forbidden, disnake.HTTPException):
            self.logger.exception("Не удалось опубликовать итоги челленджа %s", challenge["id"])
            return False

        await self.db.mark_sport_result_announced(challenge["id"])
        return True

    async def _publish_pending_results(self):
        for challenge in await self.db.get_unannounced_sport_challenges():
            await self._publish_final_results(challenge)

    @tasks.loop(seconds=60)
    async def check_sport_deadlines(self):
        try:
            await self.db.finish_expired_sport_challenges(datetime.utcnow())
            await self._publish_pending_results()
        except Exception:
            self.logger.exception("Ошибка фоновой проверки спортивных челленджей")

    @check_sport_deadlines.before_loop
    async def before_check_sport_deadlines(self):
        await self.bot.wait_until_ready()


def setup(bot, logger):
    bot.add_cog(SportCommands(bot, logger))
