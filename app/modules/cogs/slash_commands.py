import disnake
from datetime import datetime, timezone
from disnake.ext import commands

from app.modules.database import Database
from app.modules.menus.recruitment import RecruitmentView
from app.modules.modals.recruitment_setup_modal import RecruitmentSetupModal
from app.modules.scripts import Scripts


BOT_NAME = "Emiliabot"
BOT_URL = (
    "https://discord.com/api/oauth2/authorize"
    "?client_id=602393416017379328&permissions=8&scope=bot+applications.commands"
)
BOT_ICON_URL = (
    "https://media.discordapp.net/attachments/1186903406196047954/"
    "1186903657904623637/avatar_2.png"
)
FOOTER_TEXT = "Made by the_usual_god"


class SlashCommands(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.db = Database()
        self.sc = Scripts(logger, bot)

    convert_formats = commands.option_enum({"MOV": "mov", "GIF (до 10 сек)": "gif"})
    profile_asset_types = commands.option_enum({"Пользователь": "user", "Сервер": "server"})

    @commands.slash_command(
        name="ping",
        description="Понг",
    )
    async def ping(self, inter):
        await inter.response.send_message(f"Понг! {round(self.bot.latency * 1000)}мс")

    @staticmethod
    def _format_timestamp(value) -> str:
        if not value:
            return "Неизвестно"

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        timestamp = int(value.timestamp())
        return f"<t:{timestamp}:D> (<t:{timestamp}:R>)"

    @staticmethod
    def _format_status(member: disnake.Member) -> str:
        status_names = {
            disnake.Status.online: "В сети",
            disnake.Status.idle: "Отошёл",
            disnake.Status.dnd: "Не беспокоить",
            disnake.Status.offline: "Не в сети",
            disnake.Status.invisible: "Не в сети",
        }
        return status_names.get(member.status, str(member.status))

    @staticmethod
    def _format_roles(member: disnake.Member, limit: int = 12) -> str:
        roles = [
            role
            for role in sorted(member.roles, key=lambda item: item.position, reverse=True)
            if role.name != "@everyone"
        ]

        if not roles:
            return "Ролей нет"

        shown_roles = roles[:limit]
        roles_text = " ".join(role.mention for role in shown_roles)
        hidden_count = len(roles) - len(shown_roles)
        if hidden_count > 0:
            roles_text = f"{roles_text}\n+ ещё {hidden_count}"

        return roles_text

    @staticmethod
    def _format_permissions(member: disnake.Member) -> str:
        permissions = member.guild_permissions
        important_permissions = [
            ("administrator", "Администратор"),
            ("manage_guild", "Управление сервером"),
            ("manage_roles", "Управление ролями"),
            ("manage_channels", "Управление каналами"),
            ("kick_members", "Кик участников"),
            ("ban_members", "Бан участников"),
            ("manage_messages", "Управление сообщениями"),
            ("moderate_members", "Тайм-ауты"),
        ]
        enabled_permissions = [
            title
            for permission_name, title in important_permissions
            if getattr(permissions, permission_name, False)
        ]

        if not enabled_permissions:
            return "Особых прав нет"

        return "\n".join(f"• {permission}" for permission in enabled_permissions[:8])

    @staticmethod
    def _format_activities(member: disnake.Member) -> str:
        activities = [
            activity
            for activity in member.activities
            if getattr(activity, "name", None)
        ]

        if not activities:
            return "Активность не отображается"

        activity_lines = []
        for activity in activities[:3]:
            activity_type = getattr(activity, "type", None)
            if activity_type == disnake.ActivityType.playing:
                prefix = "Играет"
            elif activity_type == disnake.ActivityType.streaming:
                prefix = "Стримит"
            elif activity_type == disnake.ActivityType.listening:
                prefix = "Слушает"
            elif activity_type == disnake.ActivityType.watching:
                prefix = "Смотрит"
            elif activity_type == disnake.ActivityType.competing:
                prefix = "Соревнуется"
            else:
                prefix = "Активность"

            activity_lines.append(f"• {prefix}: {activity.name}")

        return "\n".join(activity_lines)

    @staticmethod
    def _format_badges(member: disnake.Member) -> str:
        badges = []

        if member.bot:
            badges.append("Бот")
        if member.premium_since:
            badges.append("Бустер сервера")
        if member.guild_permissions.administrator:
            badges.append("Администратор")
        if member.guild.owner_id == member.id:
            badges.append("Владелец сервера")

        return ", ".join(badges) if badges else "Без особых отметок"

    @staticmethod
    def _format_duration(total_seconds: int) -> str:
        total_seconds = max(int(total_seconds or 0), 0)
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days:
            parts.append(f"{days} д.")
        if hours:
            parts.append(f"{hours} ч.")
        if minutes:
            parts.append(f"{minutes} мин.")
        if not parts:
            parts.append(f"{seconds} сек.")

        return " ".join(parts)

    def _get_profile_stats(self, member: disnake.Member) -> dict:
        stats = self.db.get_user_stats(member.guild.id, member.id)
        total_voice_seconds = stats["total_voice_seconds"]

        if stats["voice_joined_at"]:
            active_seconds = int((datetime.utcnow() - stats["voice_joined_at"]).total_seconds())
            total_voice_seconds += max(active_seconds, 0)

        stats["total_voice_seconds"] = total_voice_seconds
        return stats

    @staticmethod
    def _format_profile_stats(stats: dict) -> str:
        voice_line = f"**В голосе:** `{SlashCommands._format_duration(stats['total_voice_seconds'])}`"
        if stats["current_voice_channel_id"]:
            voice_line = f"{voice_line}\n**Сейчас в канале:** <#{stats['current_voice_channel_id']}>"

        last_message_line = ""
        if stats["last_message_at"]:
            last_message_line = f"\n**Последнее сообщение:** {SlashCommands._format_timestamp(stats['last_message_at'])}"

        return (
            f"**Сообщений:** `{stats['message_count']}`\n"
            f"{voice_line}"
            f"{last_message_line}"
        )

    def _build_profile_embed(self, member: disnake.Member) -> disnake.Embed:
        top_role = member.top_role if member.top_role.name != "@everyone" else None
        accent_color = top_role.color.value if top_role and top_role.color.value else 0x5865F2
        display_name = member.display_name
        username = str(member)
        stats = self._get_profile_stats(member)

        embed = disnake.Embed(
            title=f"Профиль: {display_name}",
            description=f"{member.mention}\n`{username}`",
            color=accent_color,
        )
        embed.set_author(name=BOT_NAME, url=BOT_URL, icon_url=BOT_ICON_URL)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="Основное",
            value=(
                f"**Статус:** {self._format_status(member)}\n"
                f"**Отметки:** {self._format_badges(member)}\n"
                f"**Высшая роль:** {top_role.mention if top_role else 'Нет'}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Даты",
            value=(
                f"**Аккаунт создан:** {self._format_timestamp(member.created_at)}\n"
                f"**На сервере с:** {self._format_timestamp(member.joined_at)}"
            ),
            inline=False,
        )
        embed.add_field(name="Активность", value=self._format_activities(member), inline=False)
        embed.add_field(
            name="Статистика сервера",
            value=self._format_profile_stats(stats),
            inline=False,
        )
        embed.add_field(name="Роли", value=self._format_roles(member), inline=False)
        embed.add_field(name="Ключевые права", value=self._format_permissions(member), inline=True)
        embed.add_field(
            name="ID",
            value=f"**Пользователь:** `{member.id}`\n**Сервер:** `{member.guild.id}`",
            inline=True,
        )

        if member.premium_since:
            embed.add_field(
                name="Буст сервера",
                value=self._format_timestamp(member.premium_since),
                inline=False,
            )

        embed.set_footer(text=FOOTER_TEXT)
        return embed

    @commands.slash_command(
        name="profile",
        description="Показать красивый профиль участника",
        dm_permission=False,
    )
    async def profile(
        self,
        inter: disnake.GuildCommandInteraction,
        member: disnake.Member = None,
    ):
        """
        Профиль участника сервера.

        Parameters
        ----------
        member: Участник, профиль которого нужно показать. Если не указан, будет показан ваш профиль
        """
        try:
            target_member = member or inter.author
            embed = self._build_profile_embed(target_member)
            await inter.response.send_message(embed=embed)
        except Exception as e:
            await inter.response.send_message(
                "Не получилось собрать профиль пользователя.",
                ephemeral=True,
            )
            self.logger.exception(f"Ошибка в commands/profile: {e}")
            print(f"Ошибка в commands/profile: {e}")

    def _build_asset_embed(
        self,
        title: str,
        description: str,
        image_url: str,
        color: int = 0x5865F2,
    ) -> disnake.Embed:
        embed = disnake.Embed(
            title=title,
            description=description,
            color=color,
        )
        embed.set_author(name=BOT_NAME, url=BOT_URL, icon_url=BOT_ICON_URL)
        embed.set_image(url=image_url)
        embed.add_field(name="Ссылка", value=f"[Открыть изображение]({image_url})", inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        return embed

    @commands.slash_command(
        name="avatar",
        description="Показать аватар пользователя или иконку сервера",
        dm_permission=False,
    )
    async def avatar(
        self,
        inter: disnake.GuildCommandInteraction,
        asset_type: profile_asset_types = "user",
        member: disnake.Member = None,
    ):
        """
        Просмотр аватара пользователя или иконки сервера.

        Parameters
        ----------
        asset_type: Что показать: пользователя или сервер
        member: Участник, аватар которого нужно показать. Если не указан, будет показан ваш аватар
        """
        try:
            if asset_type == "server":
                if not inter.guild.icon:
                    await inter.response.send_message(
                        "У этого сервера нет иконки.",
                        ephemeral=True,
                    )
                    return

                image_url = inter.guild.icon.with_size(4096).url
                embed = self._build_asset_embed(
                    title=f"Иконка сервера: {inter.guild.name}",
                    description=f"Сервер `{inter.guild.name}`",
                    image_url=image_url,
                    color=0x2ECC71,
                )
                await inter.response.send_message(embed=embed)
                return

            target_member = member or inter.author
            avatar_asset = target_member.display_avatar.with_size(4096)
            embed = self._build_asset_embed(
                title=f"Аватар: {target_member.display_name}",
                description=f"{target_member.mention}\n`{target_member}`",
                image_url=avatar_asset.url,
                color=target_member.color.value or 0x5865F2,
            )
            await inter.response.send_message(embed=embed)
        except Exception as e:
            await inter.response.send_message(
                "Не получилось получить аватар.",
                ephemeral=True,
            )
            self.logger.exception(f"Ошибка в commands/avatar: {e}")
            print(f"Ошибка в commands/avatar: {e}")

    @commands.slash_command(
        name="banner",
        description="Показать баннер профиля или сервера",
        dm_permission=False,
    )
    async def banner(
        self,
        inter: disnake.GuildCommandInteraction,
        asset_type: profile_asset_types = "user",
        member: disnake.Member = None,
    ):
        """
        Просмотр баннера пользователя или сервера.

        Parameters
        ----------
        asset_type: Что показать: пользователя или сервер
        member: Участник, баннер которого нужно показать. Если не указан, будет показан ваш баннер
        """
        try:
            if asset_type == "server":
                if not inter.guild.banner:
                    await inter.response.send_message(
                        "У этого сервера нет баннера.",
                        ephemeral=True,
                    )
                    return

                image_url = inter.guild.banner.with_size(4096).url
                embed = self._build_asset_embed(
                    title=f"Баннер сервера: {inter.guild.name}",
                    description=f"Сервер `{inter.guild.name}`",
                    image_url=image_url,
                    color=0x9B59B6,
                )
                await inter.response.send_message(embed=embed)
                return

            target_member = member or inter.author
            user = await self.bot.fetch_user(target_member.id)
            if not user.banner:
                await inter.response.send_message(
                    f"У пользователя {target_member.mention} нет баннера профиля.",
                    ephemeral=True,
                )
                return

            image_url = user.banner.with_size(4096).url
            embed = self._build_asset_embed(
                title=f"Баннер профиля: {target_member.display_name}",
                description=f"{target_member.mention}\n`{target_member}`",
                image_url=image_url,
                color=target_member.color.value or 0x9B59B6,
            )
            await inter.response.send_message(embed=embed)
        except Exception as e:
            await inter.response.send_message(
                "Не получилось получить баннер.",
                ephemeral=True,
            )
            self.logger.exception(f"Ошибка в commands/banner: {e}")
            print(f"Ошибка в commands/banner: {e}")

    @staticmethod
    def _format_guild_owner(guild: disnake.Guild) -> str:
        owner = guild.owner
        if owner:
            return f"{owner.mention}\n`{owner}`"

        return f"`ID: {guild.owner_id}`"

    @staticmethod
    def _format_guild_verification(guild: disnake.Guild) -> str:
        verification_names = {
            "none": "Нет",
            "low": "Низкий",
            "medium": "Средний",
            "high": "Высокий",
            "highest": "Максимальный",
        }
        verification_name = getattr(guild.verification_level, "name", str(guild.verification_level))
        return verification_names.get(verification_name, verification_name)

    @staticmethod
    def _format_explicit_content_filter(guild: disnake.Guild) -> str:
        filter_names = {
            "disabled": "Отключён",
            "no_role": "Для участников без ролей",
            "all_members": "Для всех участников",
        }
        filter_name = getattr(guild.explicit_content_filter, "name", str(guild.explicit_content_filter))
        return filter_names.get(filter_name, filter_name)

    @staticmethod
    def _format_guild_boost_level(guild: disnake.Guild) -> str:
        premium_tier = getattr(guild, "premium_tier", 0)
        boost_count = getattr(guild, "premium_subscription_count", 0) or 0

        if premium_tier <= 0:
            return f"Уровень 0\nБустов: `{boost_count}`"

        return f"Уровень {premium_tier}\nБустов: `{boost_count}`"

    @staticmethod
    def _format_guild_features(guild: disnake.Guild) -> str:
        feature_names = {
            "COMMUNITY": "Сообщество",
            "DISCOVERABLE": "В поиске Discord",
            "INVITES_DISABLED": "Инвайты отключены",
            "NEWS": "Каналы объявлений",
            "PARTNERED": "Партнёр Discord",
            "VERIFIED": "Верифицирован",
            "WELCOME_SCREEN_ENABLED": "Экран приветствия",
        }
        features = [
            feature_names.get(feature, feature.replace("_", " ").title())
            for feature in getattr(guild, "features", [])
        ]

        if not features:
            return "Особых функций нет"

        return "\n".join(f"• {feature}" for feature in features[:8])

    @staticmethod
    def _count_humans_and_bots(guild: disnake.Guild) -> tuple[int, int]:
        bot_count = sum(1 for member in guild.members if member.bot)
        human_count = guild.member_count - bot_count if guild.member_count else 0
        return human_count, bot_count

    def _build_serverinfo_embed(self, guild: disnake.Guild) -> disnake.Embed:
        human_count, bot_count = self._count_humans_and_bots(guild)
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        category_count = len(guild.categories)
        role_count = max(len(guild.roles) - 1, 0)
        emoji_count = len(guild.emojis)
        sticker_count = len(getattr(guild, "stickers", []))
        accent_color = 0x5865F2

        if guild.icon:
            accent_color = 0x2ECC71

        embed = disnake.Embed(
            title=f"Сервер: {guild.name}",
            description=(
                f"**ID:** `{guild.id}`\n"
                f"**Создан:** {self._format_timestamp(guild.created_at)}"
            ),
            color=accent_color,
        )
        embed.set_author(name=BOT_NAME, url=BOT_URL, icon_url=BOT_ICON_URL)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.with_size(1024).url)
        if guild.banner:
            embed.set_image(url=guild.banner.with_size(4096).url)

        embed.add_field(name="Владелец", value=self._format_guild_owner(guild), inline=True)
        embed.add_field(
            name="Участники",
            value=(
                f"Всего: `{guild.member_count}`\n"
                f"Людей: `{human_count}`\n"
                f"Ботов: `{bot_count}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="Бусты",
            value=self._format_guild_boost_level(guild),
            inline=True,
        )
        embed.add_field(
            name="Каналы",
            value=(
                f"Текстовые: `{text_channels}`\n"
                f"Голосовые: `{voice_channels}`\n"
                f"Категории: `{category_count}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="Оформление",
            value=(
                f"Ролей: `{role_count}`\n"
                f"Эмодзи: `{emoji_count}`\n"
                f"Стикеров: `{sticker_count}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="Безопасность",
            value=(
                f"Верификация: **{self._format_guild_verification(guild)}**\n"
                f"NSFW-фильтр: **{self._format_explicit_content_filter(guild)}**"
            ),
            inline=True,
        )
        embed.add_field(name="Функции сервера", value=self._format_guild_features(guild), inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        return embed

    @commands.slash_command(
        name="serverinfo",
        description="Показать красивый профиль сервера",
        dm_permission=False,
    )
    async def serverinfo(self, inter: disnake.GuildCommandInteraction):
        """
        Профиль текущего сервера.
        """
        try:
            embed = self._build_serverinfo_embed(inter.guild)
            await inter.response.send_message(embed=embed)
        except Exception as e:
            await inter.response.send_message(
                "Не получилось собрать профиль сервера.",
                ephemeral=True,
            )
            self.logger.exception(f"Ошибка в commands/serverinfo: {e}")
            print(f"Ошибка в commands/serverinfo: {e}")

    roleMenegment = commands.option_enum({"Назначить роль": "add", "Снять роль": "take"})

    @commands.slash_command(
        name="role",
        description="Назначить/снять роль",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True, manage_roles=True),
    )
    @commands.has_permissions(administrator=True, manage_roles=True)
    async def role(
        self,
        inter: disnake.GuildCommandInteraction,
        member: disnake.Member,
        role: disnake.Role,
        action: roleMenegment,
    ):
        """
        Назначение роли участнику сервера.

        Parameters
        ----------
        member: Выберите пользователя для назначения роли
        role: Выберите роль для назначения пользователю
        action: Назначить или снять роль
        """
        try:
            if action == "add":
                await member.add_roles(role)
                await inter.response.send_message(
                    f"Роль {role.name} успешно добавлена участнику {member.display_name}."
                )
                self.logger.info(
                    f"Роль {role.name} успешно добавлена участнику {member.display_name}."
                )
            else:
                await member.remove_roles(role)
                await inter.response.send_message(
                    f"Роль {role.name} успешно снята с участника {member.display_name}."
                )
                self.logger.info(
                    f"Снятие роли {role.name} с участника {member.display_name}."
                )
        except disnake.errors.Forbidden:
            await inter.response.send_message("У меня нет прав для изменения ролей.")
            self.logger.info("Ошибка: недостаточно прав")
        except Exception as e:
            await inter.response.send_message("Произошла ошибка")
            self.logger.info(f"Произошла ошибка: {e}")

    contestStatus = commands.option_enum({"Запуск конкурса": "start", "Завершение конкурса": "stop"})

    @commands.slash_command(
        name="contest",
        description="Организация конкурса",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True),
    )
    @commands.has_permissions(administrator=True)
    async def contest(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: disnake.TextChannel,
        contest_name: str,
        emoji: disnake.Emoji,
        status: contestStatus,
        top_count: commands.Range[int, 1, 50] = 10,
    ):
        """
        Создание и завершение конкурса.

        Parameters
        ----------
        channel: Выбор канала, в котором будет проводиться или завершаться конкурс
        contest_name: Уникальное имя запуска конкурса
        emoji: Эмодзи, которая будет автоматически проставляться на новых сообщениях
        top_count: Сколько лучших мест выводить при завершении конкурса
        status: Параметр, управляющий стартом и завершением конкурса
        """
        try:
            # Даём боту время на обработку без таймаута Discord.
            await inter.response.defer(ephemeral=False)

            guild_id = inter.guild.id
            channel_id = channel.id
            emoji_str = str(emoji)
            is_start = status == "start"

            if is_start:
                contest = self.db.start_contest_run(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                    emoji_str=emoji_str,
                )
                self.db.create_update_contest(guild_id, channel_id, emoji_str, True)
                await inter.send(
                    f"Конкурс `{contest.contest_name}` в канале <#{channel_id}> активирован. "
                    f"Выбранное эмодзи: {emoji_str}",
                    ephemeral=False,
                )
            else:
                contest = self.db.stop_contest_run(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                )
                if not contest:
                    await inter.send(
                        f"Активный конкурс `{contest_name}` в канале <#{channel_id}> не найден.",
                        ephemeral=False,
                    )
                    return

                await self.sc.read_messages_with_reaction(
                    channel_id=channel_id,
                    emoji=contest.emoji_str,
                    inter=inter,
                    contest_id=contest.id,
                    top_count=top_count,
                )
                if not self.db.get_active_contests_for_channel(guild_id, channel_id):
                    self.db.create_update_contest(guild_id, channel_id, contest.emoji_str, False)
                await inter.send(
                    f"Конкурс `{contest.contest_name}` в канале <#{channel_id}> завершён.",
                    ephemeral=False,
                )
        except Exception as e:
            self.logger.exception(f"Ошибка в commands/contest: {e}")
            print(f"Ошибка в commands/contest: {e}")

    @commands.slash_command(
        name="convert",
        description="Конвертация видео",
    )
    async def convert(
        self,
        inter,
        message_id: str,
        output_format: convert_formats = "mov",
        channel: disnake.TextChannel = None,
    ):
        """
        Конвертация видео в рабочее.

        Parameters
        ----------
        message_id: id сообщения, видео которого надо сконвертировать
        channel: Канал, где находится сообщение
        """
        try:
            await inter.response.defer(ephemeral=False)
            target_channel = channel if channel else inter.channel
            message = await target_channel.fetch_message(int(message_id))

            if message.attachments:
                await self.sc.process_video_conversion(
                    inter,
                    message.attachments,
                    output_format=output_format,
                )
            else:
                await inter.followup.send("В этом сообщении нет вложений.")
        except disnake.NotFound:
            await inter.followup.send(
                "Сообщение не найдено. Убедитесь, что указан правильный ID и канал."
            )
            await inter.delete_original_response()
        except Exception as e:
            await inter.followup.send(f"Произошла ошибка: {str(e)}")
            await inter.delete_original_response()
            self.logger.exception(f"Ошибка в commands/convert: {e}")
            print(f"Ошибка в commands/convert: {e}")

    statisticStatus = commands.option_enum(
        {"Запуск сбора статистики": "start", "Завершение сбора статистики": "stop"}
    )

    @commands.slash_command(
        name="add_statistic",
        description="Статистика канала",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True, manage_roles=True),
    )
    @commands.has_permissions(administrator=True, manage_roles=True)
    async def add_statistic(
        self,
        inter,
        channel: disnake.TextChannel,
        status: statisticStatus,
    ):
        """
        Сбор статистики активности по определённому каналу.

        Parameters
        ----------
        channel: Канал для отслеживания
        status: Параметр, управляющий стартом и завершением отслеживания канала
        """
        try:
            guild_id = inter.guild.id
            channel_id = channel.id
            is_active = status == "start"

            self.db.create_update_channel_statistic(guild_id, channel_id, is_active)

            if is_active:
                await inter.send(
                    f"Отслеживание статистики в канале <#{channel_id}> активировано.",
                    ephemeral=False,
                )
            else:
                await inter.send(
                    f"Отслеживание статистики в канале <#{channel_id}> завершено",
                    ephemeral=False,
                )
        except Exception as e:
            await inter.channel.send(f"Ошибка в commands/slash_command/add_statistic: {e}")
            self.logger.exception(f"Ошибка в commands/slash_command/add_statistic: {e}")
            print(f"Ошибка в commands/slash_command/add_statistic: {e}")

    channelAnonimusMenegment = commands.option_enum(
        {"Добавить канал": "add", "Удалить канал": "del"}
    )

    @commands.slash_command(
        name="recruitment_create",
        description="Создать панель набора через модальное окно",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True),
    )
    @commands.has_permissions(administrator=True)
    async def recruitment_create(
        self,
        inter: disnake.GuildCommandInteraction,
        requests_channel: disnake.TextChannel,
        position_count: commands.Range[int, 1, 5],
        panel_channel: disnake.TextChannel = None,
    ):
        """
        Создание панели набора через модальное окно.

        Parameters
        ----------
        requests_channel: Канал, куда будут приходить заполненные заявки
        position_count: Количество должностей для выбора, от 1 до 5
        panel_channel: Канал, куда будет отправлена панель подачи заявок
        """
        try:
            target_panel_channel = panel_channel or inter.channel
            await inter.response.send_modal(
                RecruitmentSetupModal(
                    logger=self.logger,
                    requests_channel_id=requests_channel.id,
                    panel_channel_id=target_panel_channel.id,
                    position_count=position_count,
                )
            )
        except Exception as e:
            await inter.response.send_message(
                f"Ошибка при открытии настройки набора: {e}",
                ephemeral=True,
            )
            self.logger.exception(f"Ошибка в commands/recruitment_create: {e}")
            print(f"Ошибка в commands/recruitment_create: {e}")

    @commands.slash_command(
        name="add_anonimus_channel",
        description="Добавить/удалить канал из списка разрешённых для анонимных сообщений",
        dm_permission=False,
        default_member_permissions=disnake.Permissions(administrator=True),
    )
    @commands.has_permissions(administrator=True)
    async def add_anonimus_channel(
        self,
        inter: disnake.GuildCommandInteraction,
        channel: disnake.TextChannel,
        action: channelAnonimusMenegment,
    ):
        """
        Управление списком каналов для анонимных сообщений.

        Parameters
        ----------
        channel: Выберите канал для редактирования прав
        action: Выдать или забрать право на публикацию анонимных сообщений
        """
        try:
            guild_id = inter.guild.id
            channel_id = channel.id
            is_active = action == "add"

            self.db.create_update_channel_anonimus(guild_id, channel_id, is_active)

            if is_active:
                await inter.send(
                    f"Анонимные сообщения в канале <#{channel_id}> активированы.",
                    ephemeral=False,
                )
            else:
                await inter.send(
                    f"Анонимные сообщения в канале <#{channel_id}> выключены",
                    ephemeral=False,
                )
        except Exception as e:
            await inter.channel.send(f"Ошибка в commands/slash_command/channelAnonimus: {e}")
            self.logger.exception(f"Ошибка в commands/slash_command/channelAnonimus: {e}")
            print(f"Ошибка в commands/slash_command/channelAnonimus: {e}")

    @commands.slash_command(
        name="anonimuska",
        description="Отправить анонимное сообщение в этом канале",
    )
    async def send_anonimus_channel(
        self,
        inter: disnake.GuildCommandInteraction,
        message: str,
    ):
        """
        Отправка анонимного сообщения в этом канале.

        Parameters
        ----------
        message: Введите сообщение
        """
        try:
            channel_id = inter.channel.id
            anonimus_channels = self.db.get_all_anonimus_channel()

            if channel_id not in anonimus_channels:
                return await inter.response.send_message(
                    "Данный канал не поддерживает анонимные сообщения",
                    ephemeral=True,
                )

            embed = disnake.Embed(
                title="Анонимуська",
                description=message[:4096],
                color=0x00008B,
            )
            embed.set_author(
                name="Emiliabot",
                url="https://discord.com/api/oauth2/authorize?client_id=602393416017379328&permissions=8&scope=bot+applications.commands",
                icon_url="https://media.discordapp.net/attachments/1186903406196047954/1186903657904623637/avatar_2.png",
            )
            embed.set_footer(text="Made by the_usual_god")

            await inter.response.defer(ephemeral=True)
            await inter.channel.send(embed=embed)
            await inter.delete_original_response()

            self.logger.info(
                f"Анонимное сообщение от {inter.author} (ID: {inter.author.id}) "
                f"в канале {inter.channel} (ID: {channel_id}): {message[:100]}"
            )
        except Exception as e:
            error_msg = f"Ошибка при отправке анонимного сообщения: {e}"
            await inter.response.send_message(error_msg, ephemeral=True)
            self.logger.exception(f"Ошибка в commands/slash_command/send_anonimus_channel: {e}")
            print(error_msg)


def setup(bot, logger):
    bot.add_view(RecruitmentView(logger))
    bot.add_cog(SlashCommands(bot, logger))
