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
RECIPES_PAGE_SIZE = 12


def _read_positive_int_env(name: str, default: int) -> int:
    import os

    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _read_daily_reward(default: int) -> int:
    import os

    return _read_positive_int_env("DAILY_REWARD", _read_positive_int_env("ALCHEMY_DAILY_REWARD", default))


def _build_inventory_embed(inventory: dict) -> disnake.Embed:
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
    return embed


def _build_recipes_embed(guild: disnake.Guild, recipes: dict) -> disnake.Embed:
    lines = []
    for index, recipe in enumerate(recipes["items"], start=recipes["page"] * RECIPES_PAGE_SIZE + 1):
        discoverer = guild.get_member(recipe["first_discoverer_id"])
        discoverer_name = discoverer.display_name if discoverer else f"ID {recipe['first_discoverer_id']}"
        lines.append(
            f"**{index}.** `{recipe['left_element']}` + `{recipe['right_element']}` "
            f"= **{recipe['result_display']}**\nОткрыл: {discoverer_name}"
        )

    embed = disnake.Embed(
        title="Алхимия: открытые рецепты",
        description="\n\n".join(lines),
        color=0x58A65C,
    )
    embed.set_footer(
        text=(
            f"Страница {recipes['page'] + 1}/{recipes['total_pages']} "
            f"| рецептов: {recipes['total_count']}"
        )
    )
    return embed


class AlchemyPaginationView(disnake.ui.View):
    def __init__(self, author_id: int, total_pages: int) -> None:
        self.author_id = author_id
        self.current_page = 0
        self.total_pages = total_pages
        super().__init__(timeout=180)
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        has_multiple_pages = self.total_pages > 1
        self.previous_page.disabled = not has_multiple_pages or self.current_page == 0
        self.next_page.disabled = not has_multiple_pages or self.current_page >= self.total_pages - 1

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        if interaction.author.id == self.author_id:
            return True

        await interaction.response.send_message("Эти кнопки относятся к чужому списку.", ephemeral=True)
        return False

    async def refresh_page(self, interaction: disnake.MessageInteraction) -> None:
        raise NotImplementedError

    @disnake.ui.button(label="Назад", style=disnake.ButtonStyle.secondary)
    async def previous_page(
        self,
        button: disnake.ui.Button,
        interaction: disnake.MessageInteraction,
    ) -> None:
        if self.current_page > 0:
            self.current_page -= 1
        await self.refresh_page(interaction)

    @disnake.ui.button(label="Вперёд", style=disnake.ButtonStyle.primary)
    async def next_page(
        self,
        button: disnake.ui.Button,
        interaction: disnake.MessageInteraction,
    ) -> None:
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        await self.refresh_page(interaction)


class AlchemyInventoryView(AlchemyPaginationView):
    def __init__(self, db: Database, guild_id: int, user_id: int, total_pages: int) -> None:
        self.db = db
        self.guild_id = guild_id
        self.user_id = user_id
        super().__init__(author_id=user_id, total_pages=total_pages)

    async def refresh_page(self, interaction: disnake.MessageInteraction) -> None:
        inventory = self.db.get_alchemy_inventory_page(
            guild_id=self.guild_id,
            user_id=self.user_id,
            page=self.current_page,
            page_size=INVENTORY_PAGE_SIZE,
        )
        self.current_page = inventory["page"]
        self.total_pages = inventory["total_pages"]
        self._sync_buttons()
        await interaction.response.edit_message(embed=_build_inventory_embed(inventory), view=self)


class AlchemyRecipesView(AlchemyPaginationView):
    def __init__(self, db: Database, guild: disnake.Guild, author_id: int, total_pages: int) -> None:
        self.db = db
        self.guild = guild
        super().__init__(author_id=author_id, total_pages=total_pages)

    async def refresh_page(self, interaction: disnake.MessageInteraction) -> None:
        recipes = self.db.get_discovered_alchemy_recipes_page(
            guild_id=self.guild.id,
            page=self.current_page,
            page_size=RECIPES_PAGE_SIZE,
        )
        self.current_page = recipes["page"]
        self.total_pages = recipes["total_pages"]
        self._sync_buttons()
        await interaction.response.edit_message(embed=_build_recipes_embed(self.guild, recipes), view=self)


class AlchemyCommands(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db = Database()
        self.generator = AlchemyGenerator()
        self.start_balance = _read_positive_int_env("ALCHEMY_START_BALANCE", 50)
        self.daily_reward = _read_daily_reward(25)
        self.combine_cost = _read_positive_int_env("ALCHEMY_COMBINE_COST", 5)

    @commands.slash_command(
        name="alchemy_start",
        description="Начать игру в Алхимию",
        dm_permission=False,
    )
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

    @commands.slash_command(
        name="daily",
        description="Получить ежедневную валюту",
        dm_permission=False,
    )
    async def daily(self, inter: disnake.GuildCommandInteraction):
        try:
            result = self.db.claim_daily_reward(
                guild_id=inter.guild.id,
                user_id=inter.author.id,
                reward=self.daily_reward,
                today=date.today(),
            )

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
            self.logger.exception(f"Ошибка в commands/daily: {error}")
            await inter.response.send_message("Не получилось выдать дейлик.", ephemeral=True)

    @commands.slash_command(
        name="alchemy_combine",
        description="Соединить два элемента",
        dm_permission=False,
    )
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
                await inter.followup.send("Сначала начните игру командой `/alchemy_start`.", ephemeral=True)
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
                await inter.followup.send("Сначала начните игру командой `/alchemy_start`.", ephemeral=True)
                return
            if spend_result["status"] == "not_enough":
                await inter.followup.send(
                    f"Не хватает валюты. Нужно `{self.combine_cost}`, у вас `{spend_result['balance']}`. "
                    "Заберите дейлик командой `/daily`.",
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

    @commands.slash_command(
        name="alchemy_inventory",
        description="Показать вашу коллекцию элементов",
        dm_permission=False,
    )
    async def alchemy_inventory(
        self,
        inter: disnake.GuildCommandInteraction,
    ):
        try:
            inventory = self.db.get_alchemy_inventory_page(
                guild_id=inter.guild.id,
                user_id=inter.author.id,
                page=0,
                page_size=INVENTORY_PAGE_SIZE,
            )
            if inventory["status"] == "not_started":
                await inter.response.send_message("Сначала начните игру командой `/alchemy_start`.", ephemeral=True)
                return

            view = AlchemyInventoryView(
                db=self.db,
                guild_id=inter.guild.id,
                user_id=inter.author.id,
                total_pages=inventory["total_pages"],
            )
            await inter.response.send_message(
                embed=_build_inventory_embed(inventory),
                view=view,
                ephemeral=True,
            )
        except Exception as error:
            self.logger.exception(f"Ошибка в commands/alchemy_inventory: {error}")
            await inter.response.send_message("Не получилось показать коллекцию.", ephemeral=True)

    @commands.slash_command(
        name="alchemy_recipes",
        description="Показать открытые рецепты сервера",
        dm_permission=False,
    )
    async def alchemy_recipes(
        self,
        inter: disnake.GuildCommandInteraction,
    ):
        try:
            recipes = self.db.get_discovered_alchemy_recipes_page(
                guild_id=inter.guild.id,
                page=0,
                page_size=RECIPES_PAGE_SIZE,
            )
            if not recipes["items"]:
                await inter.response.send_message("На этом сервере пока нет открытых рецептов.", ephemeral=True)
                return

            view = AlchemyRecipesView(
                db=self.db,
                guild=inter.guild,
                author_id=inter.author.id,
                total_pages=recipes["total_pages"],
            )
            await inter.response.send_message(
                embed=_build_recipes_embed(inter.guild, recipes),
                view=view,
                ephemeral=True,
            )
        except Exception as error:
            self.logger.exception(f"Ошибка в commands/alchemy_recipes: {error}")
            await inter.response.send_message("Не получилось показать рецепты.", ephemeral=True)


def setup(bot, logger):
    bot.add_cog(AlchemyCommands(bot, logger))
