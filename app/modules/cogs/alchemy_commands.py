from datetime import date, timedelta

import disnake
from disnake.ext import commands

from app.modules.alchemy_service import (
    AlchemyConfigError,
    AlchemyGenerationError,
    AlchemyGenerator,
    normalize_alchemy_pair,
    validate_alchemy_word,
)
from app.modules.database import Database


BASE_ALCHEMY_ELEMENTS = [
    ("вода", "вода"),
    ("огонь", "огонь"),
    ("земля", "земля"),
    ("воздух", "воздух"),
]
INVENTORY_PAGE_SIZE = 20


def _read_positive_int_env(name: str, default: int) -> int:
    import os

    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


class AlchemyCommands(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db = Database()
        self.generator = AlchemyGenerator()
        self.start_balance = _read_positive_int_env("ALCHEMY_START_BALANCE", 50)
        self.daily_reward = _read_positive_int_env("ALCHEMY_DAILY_REWARD", 25)
        self.combine_cost = _read_positive_int_env("ALCHEMY_COMBINE_COST", 5)

    @commands.slash_command(
        name="alchemy",
        description="Мини-игра Алхимия",
        dm_permission=False,
    )
    async def alchemy(self, inter: disnake.GuildCommandInteraction):
        pass

    @alchemy.sub_command(name="start", description="Начать игру в Алхимию")
    async def alchemy_start(self, inter: disnake.GuildCommandInteraction):
        try:
            result = self.db.start_alchemy_player(
                guild_id=inter.guild.id,
                user_id=inter.author.id,
                start_balance=self.start_balance,
                base_elements=BASE_ALCHEMY_ELEMENTS,
            )

            if result["created"]:
                elements = ", ".join(name for _, name in BASE_ALCHEMY_ELEMENTS)
                await inter.response.send_message(
                    f"Профиль алхимика создан. Баланс: `{result['balance']}`. "
                    f"Стартовые элементы: {elements}."
                )
                return

            await inter.response.send_message(
                f"Профиль алхимика уже есть. Баланс: `{result['balance']}`, "
                f"элементов: `{result['element_count']}`."
            )
        except Exception as error:
            self.logger.exception(f"Ошибка в commands/alchemy_start: {error}")
            await inter.response.send_message("Не получилось создать профиль алхимика.", ephemeral=True)

    @alchemy.sub_command(name="daily", description="Получить ежедневную валюту для Алхимии")
    async def alchemy_daily(self, inter: disnake.GuildCommandInteraction):
        try:
            result = self.db.claim_alchemy_daily(
                guild_id=inter.guild.id,
                user_id=inter.author.id,
                reward=self.daily_reward,
                today=date.today(),
            )

            if result["status"] == "not_started":
                await inter.response.send_message("Сначала начните игру командой `/alchemy start`.", ephemeral=True)
                return
            if result["status"] == "already_claimed":
                tomorrow = date.today() + timedelta(days=1)
                await inter.response.send_message(
                    f"Дейлик уже забран. Следующая награда будет доступна `{tomorrow}`. "
                    f"Баланс: `{result['balance']}`.",
                    ephemeral=True,
                )
                return

            await inter.response.send_message(
                f"Вы получили `{result['reward']}` валюты. Баланс: `{result['balance']}`."
            )
        except Exception as error:
            self.logger.exception(f"Ошибка в commands/alchemy_daily: {error}")
            await inter.response.send_message("Не получилось выдать дейлик.", ephemeral=True)

    @alchemy.sub_command(name="combine", description="Соединить два элемента")
    async def alchemy_combine(
        self,
        inter: disnake.GuildCommandInteraction,
        element_1: str,
        element_2: str,
    ):
        try:
            await inter.response.defer(ephemeral=False)

            try:
                left_input = validate_alchemy_word(element_1)
                right_input = validate_alchemy_word(element_2)
            except ValueError as error:
                await inter.followup.send(f"Элементы должны быть русскими словами. {error}", ephemeral=True)
                return

            left_element, right_element = normalize_alchemy_pair(left_input, right_input)
            inventory_check = self.db.has_alchemy_elements(
                guild_id=inter.guild.id,
                user_id=inter.author.id,
                element_names=list({left_element, right_element}),
            )
            if inventory_check["status"] == "not_started":
                await inter.followup.send("Сначала начните игру командой `/alchemy start`.", ephemeral=True)
                return
            if inventory_check["missing"]:
                missing_text = ", ".join(f"`{element}`" for element in inventory_check["missing"])
                await inter.followup.send(
                    f"У вас нет нужных элементов: {missing_text}. "
                    "Открывайте новые элементы через уже доступные сочетания.",
                    ephemeral=True,
                )
                return

            spend_result = self.db.spend_alchemy_currency(
                guild_id=inter.guild.id,
                user_id=inter.author.id,
                amount=self.combine_cost,
            )
            if spend_result["status"] == "not_started":
                await inter.followup.send("Сначала начните игру командой `/alchemy start`.", ephemeral=True)
                return
            if spend_result["status"] == "not_enough":
                await inter.followup.send(
                    f"Не хватает валюты. Нужно `{self.combine_cost}`, у вас `{spend_result['balance']}`. "
                    "Заберите дейлик командой `/alchemy daily`.",
                    ephemeral=True,
                )
                return

            known_recipe = self.db.get_alchemy_recipe(inter.guild.id, left_element, right_element)
            if known_recipe:
                discovery_result = self.db.discover_known_alchemy_recipe_on_guild(
                    guild_id=inter.guild.id,
                    user_id=inter.author.id,
                    recipe_id=known_recipe["id"],
                )
                inventory_text = (
                    "Элемент добавлен в вашу коллекцию."
                    if discovery_result.get("added_to_inventory")
                    else "Этот элемент уже был в вашей коллекции."
                )
                if discovery_result["status"] == "discovered_on_guild":
                    await inter.followup.send(
                        f"`{left_element}` + `{right_element}` = **{known_recipe['result_display']}**.\n"
                        "Рецепт уже был в общей базе, поэтому GigaChat не вызывался. "
                        f"Но на этом сервере это новое открытие, {inter.author.mention} стал первооткрывателем.\n"
                        f"{inventory_text}\n"
                        f"Баланс: `{spend_result['balance']}`."
                    )
                    return

                await inter.followup.send(
                    f"`{left_element}` + `{right_element}` = **{known_recipe['result_display']}**.\n"
                    f"Этот рецепт уже был открыт на этом сервере. {inventory_text}\n"
                    f"Баланс: `{spend_result['balance']}`."
                )
                return

            try:
                generated = await self.generator.generate_result(left_element, right_element)
            except (AlchemyConfigError, AlchemyGenerationError, Exception) as error:
                refund = self.db.refund_alchemy_currency(
                    guild_id=inter.guild.id,
                    user_id=inter.author.id,
                    amount=self.combine_cost,
                    reason="combine_refund",
                )
                self.logger.exception(f"Ошибка генерации алхимии: {error}")
                await inter.followup.send(
                    "Не получилось получить результат от GigaChat. Валюта возвращена. "
                    f"Баланс: `{refund.get('balance', spend_result['balance'])}`.",
                    ephemeral=True,
                )
                return

            discovery = self.db.create_alchemy_discovery(
                guild_id=inter.guild.id,
                user_id=inter.author.id,
                left_element=left_element,
                right_element=right_element,
                result_normalized=generated["result_normalized"],
                result_display=generated["result_display"],
                openai_response_id=generated["response_id"],
            )

            if discovery["status"] == "discovered_on_guild":
                await inter.followup.send(
                    f"`{left_element}` + `{right_element}` = **{discovery['result_display']}**.\n"
                    "Рецепт уже был в общей базе, но на этом сервере открыт впервые. "
                    f"{inter.author.mention} стал первооткрывателем."
                )
                return

            if discovery["status"] == "already_discovered_on_guild":
                await inter.followup.send(
                    f"`{left_element}` + `{right_element}` = **{discovery['result_display']}**.\n"
                    "Рецепт успели открыть на этом сервере чуть раньше, поэтому первооткрытие не засчитано."
                )
                return

            await inter.followup.send(
                f"Новое открытие: `{left_element}` + `{right_element}` = **{discovery['result_display']}**.\n"
                f"{inter.author.mention} стал первооткрывателем. "
                f"Всего открытий: `{discovery['first_discovery_count']}`."
            )
        except Exception as error:
            self.logger.exception(f"Ошибка в commands/alchemy_combine: {error}")
            if inter.response.is_done():
                await inter.followup.send("Произошла ошибка при сочетании элементов.", ephemeral=True)
            else:
                await inter.response.send_message("Произошла ошибка при сочетании элементов.", ephemeral=True)

    @alchemy.sub_command(name="inventory", description="Показать вашу коллекцию элементов")
    async def alchemy_inventory(
        self,
        inter: disnake.GuildCommandInteraction,
        page: commands.Range[int, 1, 100] = 1,
    ):
        try:
            inventory = self.db.get_alchemy_inventory_page(
                guild_id=inter.guild.id,
                user_id=inter.author.id,
                page=page - 1,
                page_size=INVENTORY_PAGE_SIZE,
            )
            if inventory["status"] == "not_started":
                await inter.response.send_message("Сначала начните игру командой `/alchemy start`.", ephemeral=True)
                return

            items = ", ".join(inventory["items"]) if inventory["items"] else "Коллекция пока пустая."
            embed = disnake.Embed(
                title="Алхимия: коллекция",
                description=items,
                color=0x58A65C,
            )
            embed.set_footer(
                text=(
                    f"Страница {inventory['page'] + 1}/{inventory['total_pages']} "
                    f"| элементов: {inventory['total_count']}"
                )
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
        except Exception as error:
            self.logger.exception(f"Ошибка в commands/alchemy_inventory: {error}")
            await inter.response.send_message("Не получилось показать коллекцию.", ephemeral=True)

    @alchemy.sub_command(name="profile", description="Показать профиль алхимика")
    async def alchemy_profile(
        self,
        inter: disnake.GuildCommandInteraction,
        member: disnake.Member = None,
    ):
        try:
            target_member = member or inter.author
            profile = self.db.get_alchemy_profile(inter.guild.id, target_member.id)
            if not profile["exists"]:
                await inter.response.send_message("У этого пользователя ещё нет профиля алхимика.", ephemeral=True)
                return

            embed = disnake.Embed(
                title=f"Алхимия: {target_member.display_name}",
                color=0x58A65C,
            )
            embed.add_field(name="Баланс", value=f"`{profile['balance']}`", inline=True)
            embed.add_field(name="Элементов", value=f"`{profile['element_count']}`", inline=True)
            embed.add_field(name="Первые открытия", value=f"`{profile['first_discovery_count']}`", inline=True)
            await inter.response.send_message(embed=embed)
        except Exception as error:
            self.logger.exception(f"Ошибка в commands/alchemy_profile: {error}")
            await inter.response.send_message("Не получилось показать профиль алхимика.", ephemeral=True)

    @alchemy.sub_command(name="top", description="Топ алхимиков сервера")
    async def alchemy_top(self, inter: disnake.GuildCommandInteraction):
        try:
            rows = self.db.get_alchemy_top(inter.guild.id, limit=10)
            if not rows:
                await inter.response.send_message("В топе алхимиков пока никого нет.", ephemeral=True)
                return

            lines = []
            for index, row in enumerate(rows, start=1):
                member = inter.guild.get_member(row["user_id"])
                name = member.display_name if member else f"ID {row['user_id']}"
                lines.append(
                    f"**{index}.** {name} — открытий: `{row['first_discovery_count']}`, "
                    f"элементов: `{row['element_count']}`, баланс: `{row['balance']}`"
                )

            embed = disnake.Embed(
                title="Топ алхимиков",
                description="\n".join(lines),
                color=0x58A65C,
            )
            await inter.response.send_message(embed=embed)
        except Exception as error:
            self.logger.exception(f"Ошибка в commands/alchemy_top: {error}")
            await inter.response.send_message("Не получилось собрать топ алхимиков.", ephemeral=True)


def setup(bot, logger):
    bot.add_cog(AlchemyCommands(bot, logger))
