import asyncio
import json
import os
import random
import re
from dataclasses import dataclass

from dotenv import load_dotenv

from app.modules.alchemy_service import (
    DEFAULT_GIGACHAT_MODEL,
    _GIGACHAT_REQUEST_SEMAPHORE,
    _describe_empty_response,
    _extract_json_payload,
    _extract_response_text,
)


load_dotenv()


RARITY_WEIGHTS = {
    "common": 65,
    "uncommon": 25,
    "rare": 8,
    "legendary": 2,
}

# Версия 8 гарантирует отдельную тему для каждого нового печенья.
COOKIE_STYLE_VERSION = 8

RARITY_DIRECTIONS = {
    "common": (
        "Тихий знак",
        "лёгкая бытовая шутка с неожиданным финалом",
    ),
    "uncommon": (
        "Любопытный знак",
        "заметная ирония, абсурд или ехидная подколка",
    ),
    "rare": (
        "Яркий знак",
        "жёсткая шутка с сильным панчлайном",
    ),
    "legendary": (
        "Редкий знак",
        "максимально безумное, дерзкое и запоминающееся предсказание",
    ),
}

MAX_PREDICTION_LENGTH = 300
MAX_TITLE_LENGTH = 80
MAX_ADVICE_LENGTH = 180


class FortuneCookieConfigError(Exception):
    pass


class FortuneCookieGenerationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class FortuneCookieRecipe:
    """Во втором запросе ограничивает только редкость, не сюжет нейросети."""

    seed: int
    rarity: str


def choose_rarity(rng=None) -> str:
    """Выбирает силу знака независимо от содержимого и состояния пула."""

    rng = rng or random.SystemRandom()
    return rng.choices(
        tuple(RARITY_WEIGHTS),
        weights=tuple(RARITY_WEIGHTS.values()),
        k=1,
    )[0]


def build_fortune_cookie_recipe(seed: int, rarity: str) -> FortuneCookieRecipe:
    """Проверяет базовые параметры двухэтапной генерации."""

    if rarity not in RARITY_WEIGHTS:
        raise ValueError(f"Неизвестная редкость предсказания: {rarity}")
    return FortuneCookieRecipe(seed=seed, rarity=rarity)


def normalize_prediction_text(value: str) -> str:
    """Приводит русский текст к форме для поиска точных и близких повторов."""

    return " ".join(re.findall(r"[а-яёa-z0-9]+", value.lower()))


def _clean_single_line(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Поле «{field_name}» должно быть строкой.")
    if "\n" in value or "\r" in value:
        raise ValueError(f"Поле «{field_name}» должно состоять из одной строки.")
    cleaned = re.sub(r"\s+", " ", value.strip().strip("\"'`«»"))
    if not cleaned:
        raise ValueError(f"Поле «{field_name}» пустое.")
    return cleaned


def validate_theme_word(value: str) -> str:
    """Проверяет только технический формат свободной темы."""

    theme = _clean_single_line(value, "тема").lower()
    if not re.fullmatch(r"[а-яё]+(?:-[а-яё]+)?", theme):
        raise ValueError("Тема должна состоять из одного русского слова.")
    if not 2 <= len(theme) <= 32:
        raise ValueError("Тема должна содержать от 2 до 32 символов.")
    return theme


def validate_prediction_text(value: str, existing_texts: tuple[str, ...] = ()) -> str:
    """Проверяет только пригодность текста для БД и отсутствие точного дубля."""

    text = _clean_single_line(value, "предсказание")
    if len(text) > MAX_PREDICTION_LENGTH:
        raise ValueError("Предсказание слишком длинное.")

    normalized = normalize_prediction_text(text)
    for existing in existing_texts:
        if normalized == normalize_prediction_text(existing):
            raise ValueError("Такое предсказание уже существует.")

    return text


def validate_prediction_bundle(
    title: str,
    prediction: str,
    advice: str,
    existing_texts: tuple[str, ...] = (),
) -> tuple[str, str, str]:
    """Проверяет все видимые части печенья до сохранения в базу."""

    clean_title = _clean_single_line(title, "заголовок").rstrip(".!?:;—-")
    if len(clean_title) > MAX_TITLE_LENGTH:
        raise ValueError("Заголовок слишком длинный.")

    clean_prediction = validate_prediction_text(prediction, existing_texts)

    clean_advice = _clean_single_line(advice, "подсказка")
    if len(clean_advice) > MAX_ADVICE_LENGTH:
        raise ValueError("Подсказка слишком длинная.")

    return clean_title, clean_prediction, clean_advice


class FortuneCookieGenerator:
    """Сначала просит свободное слово, затем строит предсказание на его тему."""

    def __init__(self):
        self.model = (
            os.getenv("GIGACHAT_MODEL", DEFAULT_GIGACHAT_MODEL).strip()
            or DEFAULT_GIGACHAT_MODEL
        )
        self.attempts = self._read_attempts()
        self.config_error = None
        self.client = None
        self.chat_payload_class = None
        self.message_class = None
        self.role_class = None

        api_key = os.getenv("GIGACHAT_API_KEY")
        if not api_key:
            self.config_error = "GIGACHAT_API_KEY не задан в .env."
            return

        try:
            from gigachat import GigaChat
            from gigachat.models import Chat, Messages, MessagesRole
        except ImportError:
            self.config_error = (
                "Пакет gigachat не установлен. Установите зависимости из requirements.txt."
            )
            return

        verify_ssl_certs = os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "false").lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        self.client = GigaChat(credentials=api_key, verify_ssl_certs=verify_ssl_certs)
        self.chat_payload_class = Chat
        self.message_class = Messages
        self.role_class = MessagesRole

    @staticmethod
    def _read_attempts() -> int:
        try:
            attempts = int(os.getenv("COOKIE_GENERATION_ATTEMPTS", "6"))
        except ValueError:
            return 6
        return max(1, attempts)

    def ensure_ready(self) -> None:
        if self.config_error:
            raise FortuneCookieConfigError(self.config_error)
        if not self.client:
            raise FortuneCookieConfigError("GigaChat-клиент не инициализирован.")

    def _build_theme_prompt(
        self,
        seed: int,
        forbidden_themes: tuple[str, ...] = (),
    ):
        """Первый независимый заход: нейросеть свободно выбирает одно слово."""

        forbidden_block = ", ".join(forbidden_themes[-250:]) or "Нет."

        system_prompt = (
            "Выбери одно случайное существующее русское слово"
            "не используй словосочетания. Верни только JSON по схеме."
        )
        user_prompt = (
            f"Слово не должно совпадать ни с одной "
            f"уже использованной темой из списка: {forbidden_block}"
        )
        return self.chat_payload_class(
            model=self.model,
            messages=[
                self.message_class(role=self.role_class.SYSTEM, content=system_prompt),
                self.message_class(role=self.role_class.USER, content=user_prompt),
            ],
            max_tokens=32,
            response_format={
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {"слово": {"type": "string"}},
                    "required": ["слово"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        )

    def _build_prompt(
        self,
        recipe: FortuneCookieRecipe,
        theme: str,
        forbidden_texts: tuple[str, ...],
        rejection_notes: tuple[str, ...] = (),
    ):
        """Второй заход: нейросеть сама трактует свободно выбранную тему."""

        rarity_name, rarity_direction = RARITY_DIRECTIONS[recipe.rarity]
        forbidden_block = "\n".join(
            f"{index}. {text}"
            for index, text in enumerate(forbidden_texts[-12:], start=1)
        ) or "Нет."
        rejection_block = "\n".join(
            f"- {note}" for note in rejection_notes[-3:]
        ) or "Нет: это первая попытка."
        system_prompt = (
            "Ты комик, который пишет короткие предсказания для русскоязычного Discord-бота. "
            "Получив одно слово, истолкуй его как угодно и придумай максимально смешное "
            "предсказание с панчлайном. Главный приоритет — юмор, а не польза, доброта, реализм "
            "или правдоподобие. Можешь использовать абсурд, чёрный юмор, сарказм, грубость, мат, "
            "табуированные темы, злые и обидные подколки. Можешь шутить над читателем и любыми "
            "персонажами, оживлять предметы, ломать логику и доводить ситуацию до безумия. "
            "Не смягчай шутку, не читай мораль и не добавляй обязательный позитивный вывод. "
            "Верни только JSON по заданной схеме."
        )
        user_prompt = (
            f"Свободная тема: «{theme}».\n"
            f"Сила знака: {rarity_name} — {rarity_direction}.\n\n"
            "Полностью самостоятельно придумай трактовку, персонажей, событие и комедийный "
            "поворот. Тема — только творческий импульс, её необязательно упоминать буквально.\n\n"
            "Требования к JSON:\n"
            f"- заголовок: непустая строка, не длиннее {MAX_TITLE_LENGTH} символов;\n"
            f"- предсказание: непустая строка, не длиннее {MAX_PREDICTION_LENGTH} символов;\n"
            f"- подсказка: непустая строка, не длиннее {MAX_ADVICE_LENGTH} символов; это может быть полезный совет, "
            "вредный антисовет или дополнительный панчлайн.\n\n"
            "Никаких ограничений по теме, степени абсурда, жёсткости или обидности шутки нет.\n\n"
            f"Причины отклонения прошлых попыток:\n{rejection_block}\n\n"
            f"Не копируй и не перефразируй эти тексты:\n{forbidden_block}"
        )
        return self.chat_payload_class(
            model=self.model,
            messages=[
                self.message_class(role=self.role_class.SYSTEM, content=system_prompt),
                self.message_class(role=self.role_class.USER, content=user_prompt),
            ],
            max_tokens=320,
            response_format={
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "заголовок": {"type": "string"},
                        "предсказание": {"type": "string"},
                        "подсказка": {"type": "string"},
                    },
                    "required": ["заголовок", "предсказание", "подсказка"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        )

    def _request_theme(self, seed: int, forbidden_themes: tuple[str, ...]):
        return self.client.chat(self._build_theme_prompt(seed, forbidden_themes))

    async def _request_theme_with_limit(
        self,
        seed: int,
        forbidden_themes: tuple[str, ...],
    ):
        async with _GIGACHAT_REQUEST_SEMAPHORE:
            return await asyncio.to_thread(
                self._request_theme,
                seed,
                forbidden_themes,
            )

    def _request_prediction(
        self,
        recipe: FortuneCookieRecipe,
        theme: str,
        forbidden_texts: tuple[str, ...],
        rejection_notes: tuple[str, ...],
    ):
        return self.client.chat(
            self._build_prompt(recipe, theme, forbidden_texts, rejection_notes)
        )

    async def _request_prediction_with_limit(
        self,
        recipe: FortuneCookieRecipe,
        theme: str,
        forbidden_texts: tuple[str, ...],
        rejection_notes: tuple[str, ...],
    ):
        async with _GIGACHAT_REQUEST_SEMAPHORE:
            return await asyncio.to_thread(
                self._request_prediction,
                recipe,
                theme,
                forbidden_texts,
                rejection_notes,
            )

    async def _generate_theme(
        self,
        seed: int,
        existing_themes: tuple[str, ...] = (),
    ) -> str:
        """Получает новое слово и не допускает повтор уже использованной темы."""

        last_error = None
        rejected_themes: tuple[str, ...] = ()
        normalized_existing = {
            normalize_prediction_text(theme)
            for theme in existing_themes
            if normalize_prediction_text(theme)
        }
        for _ in range(min(3, self.attempts)):
            try:
                forbidden_themes = tuple(
                    dict.fromkeys((*existing_themes, *rejected_themes))
                )
                response = await self._request_theme_with_limit(
                    seed,
                    forbidden_themes,
                )
                output_text = _extract_response_text(response)
                if not output_text:
                    details = _describe_empty_response(response)
                    raise ValueError(f"GigaChat вернул пустую тему: {details}")
                payload = _extract_json_payload(output_text)
                theme = validate_theme_word(
                    payload.get("слово", payload.get("theme", ""))
                )
                if normalize_prediction_text(theme) in normalized_existing:
                    rejected_themes += (theme,)
                    normalized_existing.add(normalize_prediction_text(theme))
                    raise ValueError(f"Тема «{theme}» уже использовалась.")
                return theme
            except Exception as error:
                last_error = error

        raise FortuneCookieGenerationError(
            f"Не удалось выбрать тему предсказания: {last_error}"
        )

    async def generate_prediction(
        self,
        recipe: FortuneCookieRecipe,
        existing_texts: tuple[str, ...] = (),
        existing_themes: tuple[str, ...] = (),
    ) -> dict:
        self.ensure_ready()

        # Первый заход не знает будущего сюжета и выбирает только свободное слово.
        theme = await self._generate_theme(recipe.seed, existing_themes)
        rejected_texts: tuple[str, ...] = ()
        rejection_notes: tuple[str, ...] = ()
        last_error = None

        # Второй заход сам строит на выбранную тему все видимые части печенья.
        for _ in range(self.attempts):
            forbidden_texts = tuple(dict.fromkeys((*existing_texts, *rejected_texts)))
            try:
                response = await self._request_prediction_with_limit(
                    recipe,
                    theme,
                    forbidden_texts,
                    rejection_notes,
                )
            except Exception as error:
                last_error = FortuneCookieGenerationError(
                    f"Ошибка обращения к GigaChat: {error}"
                )
                continue

            output_text = _extract_response_text(response)
            if not output_text:
                details = _describe_empty_response(response)
                last_error = FortuneCookieGenerationError(
                    f"GigaChat вернул пустое предсказание: {details}."
                )
                continue

            payload = None
            try:
                payload = _extract_json_payload(output_text)
                title, prediction, advice = validate_prediction_bundle(
                    payload.get("заголовок", payload.get("title", "")),
                    payload.get("предсказание", payload.get("prediction", "")),
                    payload.get("подсказка", payload.get("advice", "")),
                    existing_texts,
                )
            except (json.JSONDecodeError, AttributeError, ValueError) as error:
                rejected_text = (
                    str(payload.get("предсказание", payload.get("prediction", "")))
                    if isinstance(payload, dict)
                    else ""
                )
                if normalize_prediction_text(rejected_text):
                    rejected_texts += (rejected_text,)
                rejection_notes += (str(error),)
                last_error = FortuneCookieGenerationError(str(error))
                continue

            return {
                "seed": recipe.seed,
                "text": prediction,
                "normalized_text": normalize_prediction_text(prediction),
                "rarity": recipe.rarity,
                "theme": theme.capitalize(),
                "setting": f"Свободная тема: {theme}",
                "tone": "свободная интерпретация",
                # Поле остаётся только ради совместимости со старой схемой БД.
                "time_horizon": "",
                # Обязательное старое поле хранит исходное слово и больше не управляет сюжетом.
                "image": theme,
                "arcana": None,
                "title": title,
                "advice": advice,
                "generation_model": self.model,
                "style_version": COOKIE_STYLE_VERSION,
            }

        raise last_error or FortuneCookieGenerationError(
            "GigaChat не смог создать достаточно цельное и уникальное предсказание."
        )
