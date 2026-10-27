import asyncio
import os
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import disnake
from disnake.ext import commands

from app.modules.fortune_cookie_service import (
    FortuneCookieConfigError,
    FortuneCookieGenerationError,
    FortuneCookieGenerator,
    build_fortune_cookie_recipe,
    choose_rarity,
)


RARITY_PRESENTATION = {
    "common": ("Обычное", 0x95A5A6),
    "uncommon": ("Необычное", 0x2ECC71),
    "rare": ("Редкое", 0x3498DB),
    "legendary": ("Легендарное", 0xF1C40F),
}


def _read_generation_percent(default: int = 10) -> int:
    try:
        value = int(os.getenv("COOKIE_NEW_PREDICTION_PERCENT", str(default)))
    except ValueError:
        return default
    return min(100, max(0, value))


def _build_cookie_embed(prediction: dict, repeated: bool = False) -> disnake.Embed:
    rarity_name, color = RARITY_PRESENTATION.get(
        prediction["rarity"],
        ("Неизвестное", 0x95A5A6),
    )
    title = "🥠 Ваше печенье на сегодня" if repeated else "🥠 Печенье открыто"
    embed = disnake.Embed(
        title=title,
        description=f"*{prediction['text']}*",
        color=color,
    )
    embed.add_field(name="Редкость", value=rarity_name, inline=True)
    embed.add_field(name="Образ", value=prediction["image"].capitalize(), inline=True)
    if prediction.get("arcana"):
        embed.add_field(name="Аркан", value=prediction["arcana"], inline=False)
    embed.set_footer(text=f"Номер предсказания: {prediction['seed']}")
    return embed


class FortuneCookieCommands(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db = bot.async_db
        self.generator = FortuneCookieGenerator()
        self.new_prediction_percent = _read_generation_percent()
        self._user_locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._generation_locks = {
            rarity: asyncio.Lock()
            for rarity in RARITY_PRESENTATION
        }

        timezone_name = os.getenv("COOKIE_TIMEZONE", "Asia/Tomsk")
        try:
            self.timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            self.logger.warning(
                "Часовой пояс COOKIE_TIMEZONE=%s не найден, используется UTC.",
                timezone_name,
            )
            self.timezone = ZoneInfo("UTC")

    def _today(self):
        return datetime.now(self.timezone).date()

    def _should_generate_prediction(self, cached_prediction: dict | None) -> bool:
        if cached_prediction is None:
            return True
        if not cached_prediction.get("arcana"):
            return True
        return secrets.randbelow(100) < self.new_prediction_percent

    async def _generate_prediction(self, rarity: str) -> dict:
        seed = secrets.randbelow(9_000_000_000_000_000_000) + 1
        recipe = build_fortune_cookie_recipe(seed, rarity)
        existing_texts = await self.db.get_recent_fortune_cookie_texts(limit=1000)
        generated = await self.generator.generate_prediction(recipe, existing_texts)
        return await self.db.create_fortune_cookie_prediction(generated)

    @commands.slash_command(
        name="cookie",
        description="Открыть печенье с предсказанием",
        dm_permission=False,
    )
    async def cookie(self, inter: disnake.GuildCommandInteraction):
        today = self._today()
        user_key = (inter.guild.id, inter.author.id)
        user_lock = self._user_locks.setdefault(user_key, asyncio.Lock())

        if user_lock.locked():
            await inter.response.send_message(
                "Ваше печенье уже открывается. Подождите немного.",
                ephemeral=True,
            )
            return

        async with user_lock:
            try:
                # Discord ждёт подтверждение interaction не дольше трёх секунд.
                # Подтверждаем команду до первого обращения к БД: оно может ждать
                # свободный поток или соединение с PostgreSQL.
                await inter.response.defer()

                current = await self.db.get_fortune_cookie_opening(
                    guild_id=inter.guild.id,
                    user_id=inter.author.id,
                    opened_on=today,
                )
                if current:
                    await inter.edit_original_response(
                        embed=_build_cookie_embed(current, repeated=True),
                    )
                    return

                rarity = choose_rarity()
                # Выбор и закрепление выполняются под одной блокировкой: пока первый
                # участник получает вариант, второй не сможет выбрать тот же самый.
                async with self._generation_locks[rarity]:
                    cached_prediction = await self.db.get_unseen_fortune_cookie_prediction(
                        guild_id=inter.guild.id,
                        user_id=inter.author.id,
                        rarity=rarity,
                        opened_on=today,
                    )
                    prediction = cached_prediction

                    if self._should_generate_prediction(cached_prediction):
                        try:
                            prediction = await self._generate_prediction(rarity)
                        except (FortuneCookieConfigError, FortuneCookieGenerationError) as error:
                            if cached_prediction is None:
                                raise
                            prediction = cached_prediction
                            self.logger.warning(
                                "Не удалось пополнить пул печенья, используется кэш: %s",
                                error,
                            )

                    if prediction is None:
                        raise FortuneCookieGenerationError("Не найдено подходящее предсказание.")

                    result = await self.db.claim_fortune_cookie_prediction(
                        guild_id=inter.guild.id,
                        user_id=inter.author.id,
                        prediction_id=prediction["id"],
                        opened_on=today,
                    )
                if result["status"] == "prediction_not_found":
                    raise FortuneCookieGenerationError("Предсказание исчезло до выдачи.")

                await inter.edit_original_response(
                    embed=_build_cookie_embed(
                        result,
                        repeated=result["status"] == "already_claimed",
                    )
                )
            except (FortuneCookieConfigError, FortuneCookieGenerationError) as error:
                self.logger.warning("Не удалось открыть печенье: %s", error)
                message = (
                    "Печенье пока не открылось: генератор предсказаний недоступен, "
                    "а подходящих вариантов в запасе ещё нет. Попробуйте позже."
                )
                if inter.response.is_done():
                    await inter.edit_original_response(content=message, embed=None)
                else:
                    await inter.response.send_message(message, ephemeral=True)
            except Exception as error:
                self.logger.exception(f"Ошибка в commands/cookie: {error}")
                message = "Не получилось открыть печенье. Попробуйте ещё раз позже."
                if inter.response.is_done():
                    await inter.edit_original_response(content=message, embed=None)
                else:
                    await inter.response.send_message(message, ephemeral=True)


def setup(bot, logger):
    bot.add_cog(FortuneCookieCommands(bot, logger))
