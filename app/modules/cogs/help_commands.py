import disnake
from disnake.ext import commands


BOT_NAME = "Emiliabot"
BOT_URL = (
    "https://discord.com/api/oauth2/authorize"
    "?client_id=602393416017379328&permissions=8&scope=bot+applications.commands"
)
BOT_ICON_URL = (
    "https://media.discordapp.net/attachments/1186903406196047954/"
    "1186903657904623637/avatar_2.png?ex=6594f12b&is=65827c2b"
    "&hm=13871565a6497e34268d14785a349ba68e87c2083dc5c2ee3dbdd21a65430a36"
    "&=&format=webp&quality=lossless"
)
FOOTER_TEXT = "Made by the_usual_god"
HELP_COMMANDS_PER_PAGE = 10
CATEGORY_ORDER = ("Справка", "Утилиты", "Музыка", "Администрирование")


# Единый каталог команд, чтобы общая и подробная справка не расходились.
COMMANDS_INFO = {
    "help": {
        "title": "/help",
        "category": "Справка",
        "kind": "Слэш-команда",
        "short": "Показывает краткую сводку по всем доступным командам и функциям бота.",
        "params": [],
        "details": [
            "Команда выводит основные разделы: справка, утилиты, администрирование, контекстные действия и автоматические функции.",
            "Для подробного описания конкретной команды используйте `/help_command`.",
        ],
        "admin_only": False,
    },
    "help_command": {
        "title": "/help_command",
        "category": "Справка",
        "kind": "Слэш-команда",
        "short": "Показывает подробное описание выбранной команды.",
        "params": [
            ("command", "Команда, по которой нужно получить подробную справку."),
        ],
        "details": [
            "Поддерживает все текущие слэш-команды бота.",
            "Контекстные команды и автоматические фоновые функции здесь не отображаются.",
        ],
        "admin_only": False,
    },
    "ping": {
        "title": "/ping",
        "category": "Утилиты",
        "kind": "Слэш-команда",
        "short": "Проверяет доступность бота и показывает текущую задержку ответа.",
        "params": [],
        "details": [
            "Подходит для быстрой проверки, отвечает ли бот на команды.",
        ],
        "admin_only": False,
    },
    "profile": {
        "title": "/profile",
        "category": "Утилиты",
        "kind": "Слэш-команда",
        "short": "Показывает красивый профиль участника с аватаром, статусом, ролями, датами и ключевыми правами.",
        "params": [
            ("member", "Участник сервера. Если не указан, бот покажет ваш профиль."),
        ],
        "details": [
            "В профиле отображаются дата создания аккаунта, дата входа на сервер, текущий статус, активности, роли, буст сервера и важные права.",
            "Также показывается статистика по серверу: количество сообщений, сообщений в день, суммарное время в голосовых каналах, голосовое время в день и последнее сообщение.",
            "Для сообщений и голосовой активности рядом со значением показывается место участника в соответствующем серверном рейтинге.",
            "Статистика начинает собираться после установки обновления и не подтягивает старую историю автоматически.",
            "Команда доступна всем участникам и работает только на сервере.",
        ],
        "admin_only": False,
    },
    "leaderboard": {
        "title": "/leaderboard",
        "category": "Утилиты",
        "kind": "Слэш-команда + кнопки",
        "short": "Показывает лидерборд участников сервера по сообщениям, голосовой активности и сроку нахождения на сервере.",
        "params": [
            (
                "leaderboard_type",
                "Какой рейтинг показать: всего сообщений, сообщений в день, голосовая активность, голосовая активность в день или старички сервера.",
            ),
        ],
        "details": [
            "Вверху лидерборда показывается текущее место пользователя, который вызвал команду.",
            "В списке выводятся никнеймы участников без упоминаний и ссылок.",
            "На одной странице показывается до 15 участников. Если данных больше, под сообщением появляются кнопки `Назад` и `Вперёд`.",
            "Кнопки листания доступны только пользователю, который вызвал команду.",
            "Статистика сообщений и голосовой активности собирается с момента установки обновления и не подтягивает старую историю автоматически.",
        ],
        "admin_only": False,
    },
    "avatar": {
        "title": "/avatar",
        "category": "Утилиты",
        "kind": "Слэш-команда",
        "short": "Показывает аватар пользователя или иконку сервера в крупном размере.",
        "params": [
            ("asset_type", "Что показать: `Пользователь` или `Сервер`. По умолчанию `Пользователь`."),
            ("member", "Участник сервера. Если не указан, бот покажет ваш аватар."),
        ],
        "details": [
            "В режиме `Пользователь` команда показывает серверный аватар участника, если он установлен, иначе обычный аватар Discord.",
            "В режиме `Сервер` команда показывает иконку текущего сервера.",
            "В ответе есть прямая ссылка на изображение.",
        ],
        "admin_only": False,
    },
    "banner": {
        "title": "/banner",
        "category": "Утилиты",
        "kind": "Слэш-команда",
        "short": "Показывает баннер профиля пользователя или баннер сервера.",
        "params": [
            ("asset_type", "Что показать: `Пользователь` или `Сервер`. По умолчанию `Пользователь`."),
            ("member", "Участник сервера. Если не указан, бот покажет ваш баннер профиля."),
        ],
        "details": [
            "В режиме `Пользователь` команда получает баннер профиля Discord.",
            "В режиме `Сервер` команда показывает баннер текущего сервера.",
            "Если баннер не установлен, бот отправит короткое личное сообщение об этом.",
        ],
        "admin_only": False,
    },
    "serverinfo": {
        "title": "/serverinfo",
        "category": "Утилиты",
        "kind": "Слэш-команда",
        "short": "Показывает красивый профиль текущего сервера с оформлением, участниками, каналами, бустами и функциями.",
        "params": [],
        "details": [
            "В профиле отображаются дата создания сервера, владелец, количество участников, людей и ботов.",
            "Команда показывает статистику каналов, ролей, эмодзи, стикеров, бустов и уровень верификации.",
            "Если у сервера есть иконка или баннер, они используются в карточке.",
        ],
        "admin_only": False,
    },
    "convert": {
        "title": "/convert",
        "category": "Утилиты",
        "kind": "Слэш-команда",
        "short": "Конвертирует вложенные видео из выбранного сообщения в MOV или GIF.",
        "params": [
            ("message_id", "ID сообщения с видео-вложением."),
            ("output_format", "Формат результата: `mov` или `gif`. По умолчанию `mov`."),
            ("channel", "Канал с исходным сообщением. Если не указан, используется текущий."),
        ],
        "details": [
            "Для GIF принимаются файлы `.mp4`, `.avi`, `.mkv`, `.mov`, `.webm`.",
            "Для MOV принимаются файлы `.mp4`, `.avi`, `.mkv`.",
            "Если GIF длиннее 10 секунд, бот ускоряет ролик, чтобы уложиться в ограничение.",
        ],
        "admin_only": False,
    },
    "anonimuska": {
        "title": "/anonimuska",
        "category": "Утилиты",
        "kind": "Слэш-команда",
        "short": "Отправляет анонимное сообщение в текущий канал от имени бота.",
        "params": [
            ("message", "Текст анонимного сообщения."),
        ],
        "details": [
            "Команда работает только в каналах, которые заранее разрешены через `/add_anonimus_channel`.",
        ],
        "admin_only": False,
    },
    "role": {
        "title": "/role",
        "category": "Администрирование",
        "kind": "Слэш-команда",
        "short": "Назначает или снимает роль у выбранного участника.",
        "params": [
            ("member", "Участник сервера."),
            ("role", "Роль для назначения или снятия."),
            ("action", "Действие: выдать роль или снять её."),
        ],
        "details": [
            "Команда доступна только администрации с правами управления ролями.",
        ],
        "admin_only": True,
    },
    "contest": {
        "title": "/contest",
        "category": "Администрирование",
        "kind": "Слэш-команда",
        "short": "Запускает или завершает конкурс в выбранном канале.",
        "params": [
            ("channel", "Канал, где проводится конкурс."),
            ("contest_name", "Уникальное имя запуска конкурса."),
            ("emoji", "Эмодзи для автоматических реакций и подсчёта голосов."),
            ("status", "Старт или завершение конкурса."),
            ("top_count", "Сколько призовых мест вывести при завершении. От 1 до 50."),
        ],
        "details": [
            "Во время активного конкурса бот автоматически ставит указанную реакцию на новые сообщения в канале.",
            "При завершении бот публикует топ сообщений, привязанных именно к этому запуску конкурса.",
        ],
        "admin_only": True,
    },
    "add_statistic": {
        "title": "/add_statistic",
        "category": "Администрирование",
        "kind": "Слэш-команда",
        "short": "Включает или выключает сбор статистики по сообщениям в канале.",
        "params": [
            ("channel", "Канал для отслеживания."),
            ("status", "Включить или выключить сбор статистики."),
        ],
        "details": [
            "Пока сбор включён, бот считает сообщения в канале.",
            "Раз в сутки бот отправляет в такой канал сводку за предыдущий день.",
        ],
        "admin_only": True,
    },
    "recruitment_create": {
        "title": "/recruitment_create",
        "category": "Администрирование",
        "kind": "Слэш-команда + модальное окно",
        "short": "Создаёт панель набора через удобное модальное окно для администрации.",
        "params": [
            ("requests_channel", "Канал, куда будут приходить заполненные заявки."),
            ("position_count", "Сколько должностей нужно добавить в меню. От 1 до 5."),
            ("panel_channel", "Канал для публикации панели набора. Если не указан, используется текущий."),
        ],
        "details": [
            "После запуска бот открывает администратору модальное окно с нужным количеством полей.",
            "Каждое поле заполняется в формате `Название | Описание`, например `Модератор | Следит за порядком`.",
            "Вертикальная черта отделяет название роли от описания.",
            "После отправки бот публикует панель с выпадающим меню для пользователей.",
        ],
        "admin_only": True,
    },
    "giveaway_create": {
        "title": "/giveaway_create",
        "category": "Администрирование",
        "kind": "Слэш-команда + модальное окно + админ-панель",
        "short": "Создаёт розыгрыш с участием по реакции и кнопкой завершения для администрации.",
        "params": [
            ("channel", "Канал, где будет опубликован розыгрыш."),
            ("emoji", "Эмодзи, по которому участники будут входить в розыгрыш."),
        ],
        "details": [
            "После запуска бот открывает модальное окно с описанием розыгрыша и количеством победителей.",
            "Бот публикует розыгрыш в выбранный канал и сразу ставит указанную реакцию.",
            "Участники добавляются и удаляются автоматически при постановке или снятии реакции.",
            "В канал, где вызвали команду, бот отправляет админ-панель со статистикой участников и кнопкой завершения.",
            "Завершать розыгрыш через кнопку может только администратор.",
            "Перед выбором победителей бот синхронизирует участников с фактическими реакциями под сообщением.",
        ],
        "admin_only": True,
    },
    "add_anonimus_channel": {
        "title": "/add_anonimus_channel",
        "category": "Администрирование",
        "kind": "Слэш-команда",
        "short": "Добавляет или убирает канал из списка разрешённых для анонимных сообщений.",
        "params": [
            ("channel", "Канал для настройки."),
            ("action", "Добавить канал в разрешённые или убрать из списка."),
        ],
        "details": [
            "После добавления участники смогут использовать `/anonimuska` в этом канале.",
        ],
        "admin_only": True,
    },
    "play": {
        "title": "/play",
        "category": "Музыка",
        "kind": "Слэш-команда",
        "short": "Включает музыку с YouTube или добавляет трек/плейлист в очередь.",
        "params": [
            ("query", "Ссылка на YouTube, ссылка на плейлист или обычный поисковый запрос. Если не указать, бот продолжит ваш сохранённый плейлист."),
        ],
        "details": [
            "Перед запуском команды нужно зайти в голосовой канал.",
            "Бот подключится к вашему каналу, найдёт трек через YouTube и начнёт проигрывание.",
            "Если музыка уже играет, трек будет добавлен в очередь.",
            "Если передана ссылка на плейлист, бот добавит в очередь все доступные треки, пока есть место в очереди.",
            "Под сообщением текущего трека есть кнопки: назад, пауза/продолжить, следующий трек и стоп.",
        ],
        "admin_only": False,
    },
    "skip": {
        "title": "/skip",
        "category": "Музыка",
        "kind": "Слэш-команда",
        "short": "Пропускает текущий трек и запускает следующий из очереди.",
        "params": [],
        "details": [
            "Если очередь пустая, после пропуска воспроизведение просто остановится.",
        ],
        "admin_only": False,
    },
    "stop": {
        "title": "/stop",
        "category": "Музыка",
        "kind": "Слэш-команда",
        "short": "Останавливает музыку и очищает личный плейлист текущего слушателя.",
        "params": [],
        "details": [
            "Команда не отключает бота от голосового канала. Для отключения используйте `/leave`.",
            "Если команду вызывает владелец текущего плейлиста, его плейлист очищается.",
            "Если команду вызывает другой человек из того же голосового канала, музыка просто останавливается без очистки чужого плейлиста.",
        ],
        "admin_only": False,
    },
    "pause": {
        "title": "/pause",
        "category": "Музыка",
        "kind": "Слэш-команда",
        "short": "Ставит текущий трек на паузу.",
        "params": [],
        "details": [
            "Работает только когда музыка уже играет.",
        ],
        "admin_only": False,
    },
    "resume": {
        "title": "/resume",
        "category": "Музыка",
        "kind": "Слэш-команда",
        "short": "Продолжает проигрывание после паузы.",
        "params": [],
        "details": [
            "Работает только если музыка была поставлена на паузу через `/pause`.",
        ],
        "admin_only": False,
    },
    "queue": {
        "title": "/queue",
        "category": "Музыка",
        "kind": "Слэш-команда",
        "short": "Показывает текущий трек и состояние вашего личного плейлиста.",
        "params": [],
        "details": [
            "В сообщении показывается текущий трек, 15 треков с текущей страницы, сколько треков осталось в вашем плейлисте и сколько недоступных треков было пропущено.",
            "Если треков больше 15, под сообщением появляются кнопки `Назад` и `Вперёд`.",
            "Команду можно вызвать без подключения к голосовому каналу.",
        ],
        "admin_only": False,
    },
    "leave": {
        "title": "/leave",
        "category": "Музыка",
        "kind": "Слэш-команда",
        "short": "Отключает бота от голосового канала.",
        "params": [],
        "details": [
            "После отключения личный плейлист не очищается. Текущий трек вернётся в ожидание, чтобы его можно было продолжить позже.",
        ],
        "admin_only": False,
    },
}


HELP_COMMAND_CHOICES = commands.option_enum(
    {
        info["title"]: command_key
        for command_key, info in COMMANDS_INFO.items()
    }
)


class HelpPaginationView(disnake.ui.View):
    def __init__(self, author_id: int, pages: list[disnake.Embed]) -> None:
        self.author_id = author_id
        self.pages = pages
        self.current_page = 0
        super().__init__(timeout=180)
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        has_multiple_pages = len(self.pages) > 1
        self.previous_page.disabled = not has_multiple_pages or self.current_page == 0
        self.next_page.disabled = (
            not has_multiple_pages or self.current_page == len(self.pages) - 1
        )

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        if interaction.author.id == self.author_id:
            return True

        await interaction.response.send_message(
            "Эти кнопки относятся к чужому сообщению `/help`. Вызовите команду сами, чтобы листать свою справку.",
            ephemeral=True,
        )
        return False

    async def _show_current_page(self, interaction: disnake.MessageInteraction) -> None:
        self._sync_buttons()
        await interaction.response.edit_message(
            embed=self.pages[self.current_page],
            view=self,
        )

    @disnake.ui.button(
        label="Назад",
        style=disnake.ButtonStyle.secondary,
        custom_id="help_previous_page",
    )
    async def previous_page(
        self,
        button: disnake.ui.Button,
        interaction: disnake.MessageInteraction,
    ) -> None:
        if self.current_page > 0:
            self.current_page -= 1

        await self._show_current_page(interaction)

    @disnake.ui.button(
        label="Вперёд",
        style=disnake.ButtonStyle.primary,
        custom_id="help_next_page",
    )
    async def next_page(
        self,
        button: disnake.ui.Button,
        interaction: disnake.MessageInteraction,
    ) -> None:
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1

        await self._show_current_page(interaction)


class Help(commands.Cog):
    def __init__(self, bot, logger) -> None:
        self.bot = bot
        self.logger = logger

    def _build_embed(
        self,
        title: str,
        description: str = "",
        page_number: int | None = None,
        total_pages: int | None = None,
    ) -> disnake.Embed:
        embed = disnake.Embed(
            title=title,
            description=description,
            color=0x00FF00,
        )
        embed.set_author(name=BOT_NAME, url=BOT_URL, icon_url=BOT_ICON_URL)
        if page_number is not None and total_pages is not None:
            embed.set_footer(text=f"{FOOTER_TEXT} | Страница {page_number}/{total_pages}")
        else:
            embed.set_footer(text=FOOTER_TEXT)
        return embed

    @staticmethod
    def _format_section(commands_info: list[tuple[str, dict]]) -> str:
        return "\n".join(
            f"**{info['title']}**{' `[админ]`' if info['admin_only'] else ''} - {info['short']}"
            for _, info in commands_info
        )

    @staticmethod
    def _get_ordered_commands() -> list[tuple[str, dict]]:
        ordered_commands = []
        for category in CATEGORY_ORDER:
            ordered_commands.extend(
                (command_key, info)
                for command_key, info in COMMANDS_INFO.items()
                if info["category"] == category
            )

        ordered_keys = {command_key for command_key, _ in ordered_commands}
        ordered_commands.extend(
            (command_key, info)
            for command_key, info in COMMANDS_INFO.items()
            if command_key not in ordered_keys
        )
        return ordered_commands

    @staticmethod
    def _chunk_commands(
        commands_info: list[tuple[str, dict]],
    ) -> list[list[tuple[str, dict]]]:
        return [
            commands_info[index:index + HELP_COMMANDS_PER_PAGE]
            for index in range(0, len(commands_info), HELP_COMMANDS_PER_PAGE)
        ]

    def _build_help_pages(self) -> list[disnake.Embed]:
        command_chunks = self._chunk_commands(self._get_ordered_commands())
        total_pages = len(command_chunks)
        pages = []

        for page_index, command_chunk in enumerate(command_chunks, start=1):
            embed = self._build_embed(
                title="Помощь по командам бота",
                description=(
                    "Здесь собраны только команды, которые можно вызвать через слэш. "
                    "Для подробностей по конкретной команде используйте `/help_command`."
                ),
                page_number=page_index,
                total_pages=total_pages,
            )
            grouped_commands: dict[str, list[tuple[str, dict]]] = {}
            for command_key, info in command_chunk:
                grouped_commands.setdefault(info["category"], []).append((command_key, info))

            for category in CATEGORY_ORDER:
                category_commands = grouped_commands.get(category, [])
                if category_commands:
                    embed.add_field(
                        name=category,
                        value=self._format_section(category_commands),
                        inline=False,
                    )

            pages.append(embed)
        return pages

    @commands.slash_command(
        name="help",
        description="Помощь по боту",
    )
    async def help(
        self,
        inter: disnake.GuildCommandInteraction,
    ):
        """
        Помощь по боту.
        """
        pages = self._build_help_pages()
        view = HelpPaginationView(author_id=inter.author.id, pages=pages)
        await inter.response.send_message(embed=pages[0], view=view)

    @commands.slash_command(
        name="help_command",
        description="Помощь по отдельным командам бота",
    )
    async def help_command(
        self,
        inter: disnake.ApplicationCommandInteraction,
        command: HELP_COMMAND_CHOICES,
    ):
        """
        Помощь по отдельным командам.

        Parameters
        ----------
        command: Интересующая команда
        """
        try:
            command_info = COMMANDS_INFO[command]
            embed = self._build_embed(title=command_info["title"])

            embed.add_field(name="Тип", value=command_info["kind"], inline=False)
            embed.add_field(name="Описание", value=command_info["short"], inline=False)
            embed.add_field(
                name="Доступ",
                value="Только администрация" if command_info["admin_only"] else "Доступно всем",
                inline=False,
            )

            if command_info["params"]:
                params_text = "\n".join(
                    f"**{param_name}**: {param_description}"
                    for param_name, param_description in command_info["params"]
                )
                embed.add_field(name="Параметры", value=params_text, inline=False)

            details_text = "\n".join(f"• {detail}" for detail in command_info["details"])
            embed.add_field(name="Подробности", value=details_text, inline=False)

            await inter.response.send_message(embed=embed)
        except Exception as e:
            self.logger.exception(f"Ошибка в help_commands/help_command: {e}")
            print(f"Ошибка в help_commands/help_command: {e}")


def setup(bot, logger):
    bot.add_cog(Help(bot, logger))
