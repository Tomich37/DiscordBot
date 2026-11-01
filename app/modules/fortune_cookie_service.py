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

# Версия 6 полностью отделяет свободную двухэтапную генерацию от старой мешалки.
COOKIE_STYLE_VERSION = 6

RARITY_DIRECTIONS = {
    "common": (
        "Тихий знак",
        "правдоподобный поворот в обычном дне без пафоса",
    ),
    "uncommon": (
        "Любопытный знак",
        "неожиданное, но жизненное совпадение",
    ),
    "rare": (
        "Яркий знак",
        "запоминающийся поворот с небанальным вторым смыслом",
    ),
    "legendary": (
        "Редкий знак",
        "особенно точное и красивое совпадение без грандиозных обещаний",
    ),
}

ALLOWED_HORIZONS = (
    "до конца дня",
    "в ближайшие два дня",
    "в течение недели",
    "при следующем удобном случае",
)

PROHIBITED_TOPICS = (
    "смерт",
    "болезн",
    "беремен",
    "расставан",
    "развод",
    "катастроф",
    "несчаст",
    "пожар",
    "выиграешь деньги",
    "разбогатеешь",
    "уволят",
)

PROHIBITED_THEME_FRAGMENTS = (
    "смерт",
    "болезн",
    "беремен",
    "развод",
    "катастроф",
    "суицид",
    "убий",
)

PROHIBITED_TEMPLATES = (
    "тебя ждёт",
    "тебя ждет",
    "судьба приготовила",
    "судьба решила",
    "судьба распорядилась",
    "звёзды говорят",
    "звезды говорят",
    "карты говорят",
    "вселенная подсказывает",
    "скоро произойдёт",
    "скоро произойдет",
    "новая возможность",
    "важный шаг",
    "всё будет хорошо",
    "все будет хорошо",
    "она подскажет",
    "он подскажет",
    "оно подскажет",
    "это подскажет",
    "она намекнёт",
    "она намекнет",
    "он намекнёт",
    "он намекнет",
)

EMPTY_ADVICE_TEMPLATES = (
    "верь в себя",
    "будь собой",
    "слушай сердце",
    "доверься судьбе",
    "не бойся перемен",
    "просто действуй",
    "мысли позитивно",
)

FUTURE_MARKERS = (
    "скоро",
    "завтра",
    "вскоре",
    "через",
    "предстоит",
    "придётся",
    "придется",
    "будет",
    "будешь",
    "будут",
    "станет",
    "станешь",
    "окажется",
    "окажешься",
    "получится",
    "удастся",
    "к вечеру",
    "к концу",
    "до конца",
    "обнаружишь",
    "получишь",
    "встретишь",
    "найдёшь",
    "найдешь",
    "заметишь",
    "решишь",
    "поймёшь",
    "поймешь",
    "поможет",
    "подскажет",
    "напомнит",
    "появится",
    "случится",
    "закончится",
    "изменится",
)

SIMILARITY_THRESHOLD = 0.68
MIN_PREDICTION_WORDS = 16
MAX_PREDICTION_WORDS = 42
MAX_PREDICTION_LENGTH = 360
MIN_TITLE_WORDS = 2
MAX_TITLE_WORDS = 6
MIN_ADVICE_WORDS = 4
MAX_ADVICE_WORDS = 16


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


def prediction_similarity(left: str, right: str) -> float:
    """Сравнивает словарь и соседние пары слов, не полагаясь на пунктуацию."""

    def features(value: str) -> set[str]:
        words = normalize_prediction_text(value).split()
        unigrams = {f"w:{word}" for word in words}
        bigrams = {
            f"b:{left_word}_{right_word}"
            for left_word, right_word in zip(words, words[1:])
        }
        return unigrams | bigrams

    left_features = features(left)
    right_features = features(right)
    if not left_features or not right_features:
        return 0.0
    return len(left_features & right_features) / len(left_features | right_features)


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
    """Принимает одно безопасное русское слово из первого запроса."""

    theme = _clean_single_line(value, "тема").lower()
    if not re.fullmatch(r"[а-яё]+(?:-[а-яё]+)?", theme):
        raise ValueError("Тема должна состоять из одного русского слова.")
    if not 2 <= len(theme) <= 32:
        raise ValueError("Тема должна содержать от 2 до 32 символов.")
    if any(fragment in theme for fragment in PROHIBITED_THEME_FRAGMENTS):
        raise ValueError("Для темы выбрано небезопасное слово.")
    return theme


def _contains_future_marker(normalized_text: str) -> bool:
    padded_text = f" {normalized_text} "
    return any(f" {marker} " in padded_text for marker in FUTURE_MARKERS)


def validate_prediction_text(value: str, existing_texts: tuple[str, ...] = ()) -> str:
    """Проверяет прогноз: конкретность, безопасность и отличие от старых текстов."""

    text = _clean_single_line(value, "предсказание")
    if len(text) > MAX_PREDICTION_LENGTH:
        raise ValueError("Предсказание слишком длинное.")

    words = re.findall(r"[а-яёa-z0-9-]+", text.lower())
    if not MIN_PREDICTION_WORDS <= len(words) <= MAX_PREDICTION_WORDS:
        raise ValueError(
            "Предсказание должно содержать "
            f"от {MIN_PREDICTION_WORDS} до {MAX_PREDICTION_WORDS} слов."
        )

    normalized = normalize_prediction_text(text)
    if any(fragment in normalized for fragment in PROHIBITED_TOPICS):
        raise ValueError("Предсказание затрагивает запрещённую серьёзную тему.")
    if any(template in normalized for template in PROHIBITED_TEMPLATES):
        raise ValueError("Предсказание использует шаблонную формулировку.")
    if not _contains_future_marker(normalized):
        raise ValueError("Предсказание не описывает будущее событие или последствие.")

    for existing in existing_texts:
        if normalized == normalize_prediction_text(existing):
            raise ValueError("Такое предсказание уже существует.")
        if prediction_similarity(text, existing) >= SIMILARITY_THRESHOLD:
            raise ValueError("Предсказание слишком похоже на существующее.")

    return text


def validate_prediction_bundle(
    title: str,
    prediction: str,
    advice: str,
    horizon: str,
    existing_texts: tuple[str, ...] = (),
) -> tuple[str, str, str, str]:
    """Проверяет все видимые части печенья до сохранения в базу."""

    clean_title = _clean_single_line(title, "заголовок").rstrip(".!?:;—-")
    title_words = re.findall(r"[а-яёa-z0-9-]+", clean_title.lower())
    if not MIN_TITLE_WORDS <= len(title_words) <= MAX_TITLE_WORDS:
        raise ValueError(
            f"Заголовок должен содержать от {MIN_TITLE_WORDS} до {MAX_TITLE_WORDS} слов."
        )
    if len(clean_title) > 80:
        raise ValueError("Заголовок слишком длинный.")

    clean_prediction = validate_prediction_text(prediction, existing_texts)

    clean_advice = _clean_single_line(advice, "подсказка")
    advice_words = re.findall(r"[а-яёa-z0-9-]+", clean_advice.lower())
    if not MIN_ADVICE_WORDS <= len(advice_words) <= MAX_ADVICE_WORDS:
        raise ValueError(
            f"Подсказка должна содержать от {MIN_ADVICE_WORDS} до {MAX_ADVICE_WORDS} слов."
        )
    if len(clean_advice) > 180:
        raise ValueError("Подсказка слишком длинная.")
    normalized_advice = normalize_prediction_text(clean_advice)
    if any(template in normalized_advice for template in EMPTY_ADVICE_TEMPLATES):
        raise ValueError("Подсказка получилась слишком общей.")
    if any(fragment in normalized_advice for fragment in PROHIBITED_TOPICS):
        raise ValueError("Подсказка затрагивает запрещённую серьёзную тему.")

    clean_horizon = _clean_single_line(horizon, "срок").lower()
    if clean_horizon not in ALLOWED_HORIZONS:
        raise ValueError("Указан неподдерживаемый срок предсказания.")

    return clean_title, clean_prediction, clean_advice, clean_horizon


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

    def _build_theme_prompt(self, seed: int):
        """Первый независимый заход: нейросеть свободно выбирает одно слово."""

        system_prompt = (
            "Выбери одно случайное существующее русское слово любой части речи, на тему которого "
            "затем можно написать короткое предсказание. Слово может быть конкретным или "
            "абстрактным, обычным или неожиданным. Не выдумывай неологизм, не объясняй выбор, "
            "не используй имена собственные, тяжёлые темы и словосочетания. Верни только JSON "
            "по схеме."
        )
        user_prompt = (
            f"Случайный идентификатор: {seed}. Выбери любое новое выразительное слово. "
            "Не пытайся превращать цифры в смысл."
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
        horizons = ", ".join(f"«{value}»" for value in ALLOWED_HORIZONS)

        system_prompt = (
            "Ты редактор коротких предсказаний для русскоязычного Discord-бота. Получив одно "
            "слово, свободно истолкуй его как образ, ситуацию, действие, настроение или метафору. "
            "Не вставляй слово механически и не обязан использовать его буквально. Сам придумай "
            "весь сюжет. Предсказание должно быть цельной правдоподобной сценой из ближайшего "
            "будущего, а не настоящим гаданием. Не упоминай Таро, звёзды, судьбу и магию. "
            "Не обещай деньги, любовь, здоровье или другие серьёзные события. Заголовок, прогноз "
            "и подсказка должны относиться к одной придуманной тобой ситуации. Пиши естественным "
            "современным русским языком, обращайся на «ты», избегай пафоса и гороскопных клише. "
            "Не наделяй предметы, еду, животных и погоду способностью советовать, выбирать, "
            "намекать или предсказывать: поворот должен вытекать из действий и слов людей. "
            "Верни только JSON по заданной схеме."
        )
        user_prompt = (
            f"Свободная тема: «{theme}».\n"
            f"Сила знака: {rarity_name} — {rarity_direction}.\n\n"
            "Полностью самостоятельно придумай трактовку, место, участников, событие, настроение "
            "и поворот. Тема — только творческий импульс, а не список обязательных деталей.\n\n"
            "Требования к JSON:\n"
            f"- заголовок: от {MIN_TITLE_WORDS} до {MAX_TITLE_WORDS} слов; живой заголовок без точки.\n"
            f"- предсказание: от {MIN_PREDICTION_WORDS} до {MAX_PREDICTION_WORDS} слов, одна или две "
            "связанные фразы. Обязательно опиши то, что ещё произойдёт, и добавь конкретную "
            "наблюдаемую деталь. Не начинай с «Сегодня» или «Скоро».\n"
            f"- подсказка: от {MIN_ADVICE_WORDS} до {MAX_ADVICE_WORDS} слов; одно выполнимое действие "
            "для этой же ситуации, а не общая мораль.\n"
            f"- срок: выбери ровно один вариант: {horizons}.\n\n"
            "Можно быть тёплым, ироничным, загадочным или неожиданным — выбери сам. Предмет может "
            "быть деталью сцены, но не источником совета или знака. Не объясняй связь с исходным "
            "словом. Не называй конкретный день недели или календарную дату: они могут не "
            "совпасть с выбранным сроком.\n\n"
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
                        "срок": {
                            "type": "string",
                            "enum": list(ALLOWED_HORIZONS),
                        },
                    },
                    "required": ["заголовок", "предсказание", "подсказка", "срок"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        )

    def _request_theme(self, seed: int):
        return self.client.chat(self._build_theme_prompt(seed))

    async def _request_theme_with_limit(self, seed: int):
        async with _GIGACHAT_REQUEST_SEMAPHORE:
            return await asyncio.to_thread(self._request_theme, seed)

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

    async def _generate_theme(self, seed: int) -> str:
        """Получает слово первым запросом и отдельно проверяет его формат."""

        last_error = None
        for _ in range(min(3, self.attempts)):
            try:
                response = await self._request_theme_with_limit(seed)
                output_text = _extract_response_text(response)
                if not output_text:
                    details = _describe_empty_response(response)
                    raise ValueError(f"GigaChat вернул пустую тему: {details}")
                payload = _extract_json_payload(output_text)
                return validate_theme_word(
                    payload.get("слово", payload.get("theme", ""))
                )
            except Exception as error:
                last_error = error

        raise FortuneCookieGenerationError(
            f"Не удалось выбрать тему предсказания: {last_error}"
        )

    async def generate_prediction(
        self,
        recipe: FortuneCookieRecipe,
        existing_texts: tuple[str, ...] = (),
    ) -> dict:
        self.ensure_ready()

        # Первый заход не знает будущего сюжета и выбирает только свободное слово.
        theme = await self._generate_theme(recipe.seed)
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
                title, prediction, advice, horizon = validate_prediction_bundle(
                    payload.get("заголовок", payload.get("title", "")),
                    payload.get("предсказание", payload.get("prediction", "")),
                    payload.get("подсказка", payload.get("advice", "")),
                    payload.get("срок", payload.get("horizon", "")),
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
                "time_horizon": horizon,
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
