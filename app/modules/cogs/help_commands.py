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
            "Также показывает описание контекстных команд для конвертации видео.",
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
    "context_convert_video": {
        "title": "Convert Video",
        "category": "Контекстные команды",
        "kind": "Команда сообщения",
        "short": "Конвертирует вложенные видео из выбранного сообщения в MOV.",
        "params": [],
        "details": [
            "Вызывается через меню действий у сообщения в Discord.",
            "Удобна, когда не хочется вручную копировать `message_id` в `/convert`.",
        ],
        "admin_only": False,
    },
    "context_convert_video_to_gif": {
        "title": "Convert Video to GIF",
        "category": "Контекстные команды",
        "kind": "Команда сообщения",
        "short": "Конвертирует вложенные видео из выбранного сообщения в GIF.",
        "params": [],
        "details": [
            "Вызывается через меню действий у сообщения в Discord.",
            "Использует те же ограничения на длительность GIF, что и `/convert`.",
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


class Help(commands.Cog):
    def __init__(self, bot, logger) -> None:
        self.bot = bot
        self.logger = logger

    def _build_embed(self, title: str, description: str = "") -> disnake.Embed:
        embed = disnake.Embed(
            title=title,
            description=description,
            color=0x00FF00,
        )
        embed.set_author(name=BOT_NAME, url=BOT_URL, icon_url=BOT_ICON_URL)
        embed.set_footer(text=FOOTER_TEXT)
        return embed

    @staticmethod
    def _format_section(commands_info: list[tuple[str, dict]]) -> str:
        return "\n".join(
            f"**{info['title']}**{' `[админ]`' if info['admin_only'] else ''} - {info['short']}"
            for _, info in commands_info
        )

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
        embed = self._build_embed(
            title="Помощь по командам и функциям бота",
            description=(
                "Ниже собраны все текущие команды и встроенные функции бота. "
                "Для подробностей по конкретной команде используйте `/help_command`."
            ),
        )

        grouped_commands: dict[str, list[tuple[str, dict]]] = {}
        for command_key, info in COMMANDS_INFO.items():
            grouped_commands.setdefault(info["category"], []).append((command_key, info))

        for category in ("Справка", "Утилиты", "Администрирование", "Контекстные команды"):
            commands_info = grouped_commands.get(category, [])
            if commands_info:
                embed.add_field(
                    name=category,
                    value=self._format_section(commands_info),
                    inline=False,
                )
                
        await inter.response.send_message(embed=embed)

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
            self.logger.error(f"Ошибка в help_commands/help_command: {e}")
            print(f"Ошибка в help_commands/help_command: {e}")


def setup(bot, logger):
    bot.add_cog(Help(bot, logger))
