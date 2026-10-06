import disnake


# Эти команды сами управляют первым ответом: открывают форму либо редактируют
# заранее отложенный ответ. Общая оболочка не должна отвечать раньше них.
SLASH_COMMANDS_WITH_CUSTOM_RESPONSE = frozenset({
    "alchemy_combine",
    "anonimuska",
    "contest",
    "convert",
    "giveaway_create",
    "play",
    "recruitment_create",
})


async def acknowledge_slash_command_response(bot, inter, command_name: str) -> None:
    """Сразу подтверждает обычную команду, чтобы Discord не закрыл её через 3 секунды."""
    if command_name in SLASH_COMMANDS_WITH_CUSTOM_RESPONSE:
        return

    if inter.response.is_done():
        return

    await inter.response.send_message("Обрабатываю команду…", ephemeral=True)
    bot._automatically_acknowledged_interactions.add(inter.id)


async def send_interaction_response(inter, *args, **kwargs):
    """Сохраняет требуемую видимость после автоматического подтверждения команды."""
    acknowledged_interactions = getattr(
        inter.bot,
        "_automatically_acknowledged_interactions",
        set(),
    )
    if inter.id not in acknowledged_interactions:
        return await inter.send(*args, **kwargs)

    if kwargs.get("ephemeral", False):
        edit_kwargs = dict(kwargs)
        edit_kwargs.pop("ephemeral", None)
        edit_kwargs.pop("tts", None)
        result = await inter.edit_original_response(*args, **edit_kwargs)
        acknowledged_interactions.discard(inter.id)
        return result

    # Приватную заглушку нельзя превратить в публичное сообщение. Удаляем её,
    # а результат отправляем отдельным публичным follow-up.
    try:
        await inter.delete_original_response()
    except disnake.NotFound:
        pass

    result = await inter.followup.send(*args, **kwargs)
    acknowledged_interactions.discard(inter.id)
    return result


async def cleanup_slash_command_response(bot, inter, command_name: str) -> None:
    """Убирает служебное «бот думает» после отправки результата через follow-up."""
    if inter.id not in bot._automatically_acknowledged_interactions:
        return

    bot._automatically_acknowledged_interactions.discard(inter.id)
    try:
        await inter.delete_original_response()
    except disnake.NotFound:
        pass
    except disnake.HTTPException as error:
        bot.logger.warning(
            "Не удалось убрать служебный ответ команды /%s: %s",
            command_name,
            error,
        )
