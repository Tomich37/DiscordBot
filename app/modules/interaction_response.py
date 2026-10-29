SLASH_COMMANDS_WITH_CUSTOM_RESPONSE = frozenset({
    "alchemy_combine",
    "anonimuska",
    "contest",
    "convert",
    "cookie",
    "giveaway_create",
    "play",
    "recruitment_create",
})

EPHEMERAL_SLASH_COMMANDS = frozenset({
    "alchemy_inventory",
    "alchemy_recipes",
    "balance",
    "sport add",
    "sport create",
    "sport finish",
    "sport join",
})


def get_interaction_command_name(inter) -> str:
    """Извлекает полный путь команды из payload Discord: например, `sport add`."""

    data = getattr(inter, "data", None)
    root_name = getattr(data, "name", None)
    if root_name:
        # У объектов Disnake этот метод штатно возвращает цепочку групп и подкоманд.
        chain_getter = getattr(data, "_get_chain_and_kwargs", None)
        if callable(chain_getter):
            chain, _ = chain_getter()
            return " ".join((root_name, *chain))

        # Запасной путь полезен для совместимости и тестовых interaction-объектов.
        command_parts = [root_name]
        options = getattr(data, "options", None) or []
        while options:
            option = options[0]
            value = getattr(option, "value", None)
            if value is not None:
                break
            option_name = getattr(option, "name", None)
            if not option_name:
                break
            command_parts.append(option_name)
            options = getattr(option, "options", None) or []
        return " ".join(command_parts)

    command = getattr(inter, "application_command", None)
    if command and getattr(command, "qualified_name", None):
        return command.qualified_name
    if command and getattr(command, "name", None):
        return command.name

    if data and getattr(data, "custom_id", None):
        return data.custom_id
    return "неизвестно"


async def acknowledge_slash_command(bot, inter, command_name: str) -> None:
    """Подтверждает обычную слеш-команду до начала долгой работы."""
    root_command_name = command_name.split(maxsplit=1)[0]
    if (
        command_name in SLASH_COMMANDS_WITH_CUSTOM_RESPONSE
        or root_command_name in SLASH_COMMANDS_WITH_CUSTOM_RESPONSE
        or inter.response.is_done()
    ):
        return

    ephemeral = command_name in EPHEMERAL_SLASH_COMMANDS
    await inter.response.defer(ephemeral=ephemeral)
    bot._deferred_interactions[inter.id] = ephemeral


async def send_interaction_response(inter, *args, **kwargs):
    """Редактирует отложенный ответ либо отправляет обычный ответ interaction."""
    deferred_interactions = getattr(
        inter.bot,
        "_deferred_interactions",
        {},
    )
    if inter.id not in deferred_interactions:
        return await inter.send(*args, **kwargs)

    deferred_ephemeral = deferred_interactions[inter.id]
    requested_ephemeral = kwargs.get("ephemeral", False)
    if requested_ephemeral != deferred_ephemeral:
        status = (
            "Результат отправлен отдельным сообщением."
            if deferred_ephemeral
            else "Запрос обработан. Подробности доступны только вам."
        )
        # Сначала завершаем отложенный ответ, иначе Discord может принять
        # первый follow-up за него и проигнорировать его флаг приватности.
        await inter.edit_original_response(content=status, embed=None, view=None)
        result = await inter.followup.send(*args, **kwargs)
        deferred_interactions.pop(inter.id, None)
        return result

    edit_kwargs = dict(kwargs)
    edit_kwargs.pop("ephemeral", None)
    edit_kwargs.pop("tts", None)
    result = await inter.edit_original_response(*args, **edit_kwargs)
    deferred_interactions.pop(inter.id, None)
    return result


def clear_deferred_interaction_response(bot, inter) -> None:
    """Освобождает отметку после завершения обработчика команды."""
    bot._deferred_interactions.pop(inter.id, None)
