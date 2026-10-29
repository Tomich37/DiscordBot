import asyncio
import json
import os
import random
import re
from dataclasses import asdict, dataclass

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

COOKIE_STYLE_VERSION = 2

MAJOR_ARCANA = (
    "0 — Шут",
    "I — Маг",
    "II — Верховная Жрица",
    "III — Императрица",
    "IV — Император",
    "V — Иерофант",
    "VI — Влюблённые",
    "VII — Колесница",
    "VIII — Сила",
    "IX — Отшельник",
    "X — Колесо Фортуны",
    "XI — Справедливость",
    "XII — Повешенный",
    "XIII — Смерть",
    "XIV — Умеренность",
    "XV — Дьявол",
    "XVI — Башня",
    "XVII — Звезда",
    "XVIII — Луна",
    "XIX — Солнце",
    "XX — Суд",
    "XXI — Мир",
)

MINOR_ARCANA_RANKS = (
    "Туз",
    "Двойка",
    "Тройка",
    "Четвёрка",
    "Пятёрка",
    "Шестёрка",
    "Семёрка",
    "Восьмёрка",
    "Девятка",
    "Десятка",
    "Паж",
    "Рыцарь",
    "Королева",
    "Король",
)

MINOR_ARCANA_SUITS = ("Жезлов", "Кубков", "Мечей", "Пентаклей")
MINOR_ARCANA = tuple(
    f"{rank} {suit}"
    for suit in MINOR_ARCANA_SUITS
    for rank in MINOR_ARCANA_RANKS
)
TAROT_ARCANA = MAJOR_ARCANA + MINOR_ARCANA

THEMES = (
    "дружба",
    "творчество",
    "работа или учёба",
    "отдых",
    "неожиданная встреча",
    "маленькая удача",
    "новое увлечение",
    "полезная привычка",
    "решение старой задачи",
    "приятная новость",
    "неловкое совпадение",
    "маленький бытовой триумф",
    "внезапный перекус",
    "спор с техникой",
    "безобидный хаос",
    "подозрительно удачный момент",
    "давно забытая вещь",
    "случайная фраза",
    "странный комплимент",
    "план, пошедший не по плану",
    "победа над будильником",
    "неожиданно полезная лень",
    "маленькое приключение",
    "смешное недоразумение",
)

SETTINGS = (
    "в дороге",
    "дома",
    "в интернете",
    "во время разговора",
    "в непривычном месте",
    "среди знакомых людей",
    "во время обычного дела",
    "в момент отдыха",
    "на кухне",
    "в очереди",
    "в лифте",
    "в магазине",
    "в общественном транспорте",
    "в групповом чате",
    "рядом с холодильником",
    "перед сном",
    "после неожиданного уведомления",
    "во время поиска потерянной вещи",
    "на встрече",
    "когда планы внезапно меняются",
)

TONES = (
    "добродушный",
    "загадочный",
    "ироничный",
    "вдохновляющий",
    "слегка абсурдный",
    "уютный",
    "озорно-добродушный",
    "сухо-ироничный",
    "комедийно-драматичный",
    "по-дружески ехидный",
    "абсурдно-торжественный",
    "мемный, но понятный без знания мемов",
)

TIME_HORIZONS = (
    "сегодня",
    "в ближайшие несколько дней",
    "на этой неделе",
    "совсем скоро",
)

IMAGES = (
    "ключ",
    "фонарь",
    "чашка",
    "письмо",
    "дождь",
    "кот",
    "поезд",
    "звезда",
    "мост",
    "окно",
    "карта",
    "звонок",
    "зонт",
    "носок",
    "чайник",
    "будильник",
    "кактус",
    "ложка",
    "вилка",
    "холодильник",
    "микроволновка",
    "лифт",
    "трамвай",
    "велосипед",
    "самокат",
    "чемодан",
    "рюкзак",
    "чек из магазина",
    "наклейка",
    "пуговица",
    "шнурок",
    "шляпа",
    "варежка",
    "шарф",
    "кроссовок",
    "тапок",
    "воздушный шар",
    "зеркало",
    "расчёска",
    "зубная щётка",
    "кусок мыла",
    "резиновая уточка",
    "пицца",
    "пельмень",
    "лимон",
    "арбуз",
    "бутерброд",
    "лапша",
    "банка варенья",
    "банан",
    "ананас",
    "морковка",
    "пончик",
    "торт",
    "попкорн",
    "автомат с напитками",
    "тележка из магазина",
    "посылка",
    "почтовый ящик",
    "светофор",
    "дорожный знак",
    "скамейка",
    "лестница",
    "дверь",
    "замочная скважина",
    "крыша",
    "балкон",
    "подвал",
    "чердак",
    "лужа",
    "сугроб",
    "облако",
    "радуга",
    "гром",
    "ветер",
    "луна",
    "комета",
    "планета",
    "спутник",
    "робот",
    "дракон",
    "привидение",
    "пингвин",
    "капибара",
    "гусь",
    "енот",
    "хомяк",
    "сова",
    "ворон",
    "шмель",
    "бабочка",
    "улитка",
    "лягушка",
    "рыба",
    "медуза",
    "динозавр",
    "единорог",
    "пират",
    "рыцарь",
    "волшебник",
    "корона",
    "меч",
    "щит",
    "компас",
    "песочные часы",
    "настенные часы",
    "календарь",
    "монета",
    "игральный кубик",
    "шахматный конь",
    "игральная карта",
    "книга",
    "блокнот",
    "карандаш",
    "маркер",
    "ластик",
    "бумажный самолётик",
    "виниловая пластинка",
    "наушники",
    "микрофон",
    "фотоаппарат",
    "проектор",
    "диско-шар",
    "фейерверк",
    "мыльный пузырь",
    "магнит",
    "батарейка",
    "флешка",
    "пароль",
    "мем",
    "уведомление",
    "значок Wi-Fi",
    "полоса загрузки",
    "курсор",
    "клавиатура",
    "пробел на клавиатуре",
    "скриншот",
    "эмодзи",
)

STRUCTURES = (
    "серьёзное начало и нелепая бытовая развязка",
    "безобидная тревога, которая оборачивается удачей",
    "эпическое предзнаменование о совершенно обычной вещи",
    "игривое предупреждение с полезной подсказкой",
    "абсурдная причина и неожиданно логичное следствие",
    "предмет ведёт себя как персонаж и вмешивается в день",
    "смешное правило дня, которое хочется проверить",
    "добрая подколка без унижения и грубости",
    "короткая ироничная примета с панчлайном",
    "неожиданная награда за маленькую бытовую ошибку",
    "ложно торжественное пророчество с приземлённым финалом",
    "забавное совпадение, которое окажется полезным",
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
    "скоро произойдёт",
    "скоро произойдет",
    "осветит путь",
    "подсветит путь",
    "новая возможность",
    "верное направление",
    "важный шаг",
    "привычный маршрут",
)

SIMILARITY_THRESHOLD = 0.72
MIN_WORDS = 8
MAX_WORDS = 22
MAX_LENGTH = 240


class FortuneCookieConfigError(Exception):
    pass


class FortuneCookieGenerationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class FortuneCookieRecipe:
    seed: int
    rarity: str
    theme: str
    setting: str
    tone: str
    time_horizon: str
    image: str
    arcana: str
    structure: str


def choose_rarity(rng=None) -> str:
    """Выбирает редкость независимо от содержимого и состояния пула."""

    rng = rng or random.SystemRandom()
    rarities = tuple(RARITY_WEIGHTS)
    weights = tuple(RARITY_WEIGHTS.values())
    return rng.choices(rarities, weights=weights, k=1)[0]


def build_fortune_cookie_recipe(seed: int, rarity: str) -> FortuneCookieRecipe:
    """Строит один и тот же набор творческих ограничений для одинакового seed."""

    if rarity not in RARITY_WEIGHTS:
        raise ValueError(f"Неизвестная редкость предсказания: {rarity}")

    rng = random.Random(seed)
    return FortuneCookieRecipe(
        seed=seed,
        rarity=rarity,
        theme=rng.choice(THEMES),
        setting=rng.choice(SETTINGS),
        tone=rng.choice(TONES),
        time_horizon=rng.choice(TIME_HORIZONS),
        image=rng.choice(IMAGES),
        arcana=rng.choice(TAROT_ARCANA),
        structure=rng.choice(STRUCTURES),
    )


def normalize_prediction_text(value: str) -> str:
    """Приводит текст к форме, пригодной для точного поиска дублей."""

    return " ".join(re.findall(r"[а-яёa-z0-9]+", value.lower()))


def prediction_similarity(left: str, right: str) -> float:
    """Оценивает лексическое сходство двух предсказаний по Жаккару."""

    left_words = set(normalize_prediction_text(left).split())
    right_words = set(normalize_prediction_text(right).split())
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / len(left_words | right_words)


def validate_prediction_text(value: str, existing_texts: tuple[str, ...] = ()) -> str:
    """Проверяет формат, безопасный тон и отсутствие заметных повторов."""

    text = re.sub(r"\s+", " ", value.strip().strip("\"'`«»"))
    if not text:
        raise ValueError("Предсказание пустое.")
    if len(text) > MAX_LENGTH:
        raise ValueError("Предсказание слишком длинное.")
    if "\n" in value:
        raise ValueError("Предсказание должно состоять из одной строки.")

    words = re.findall(r"[а-яёa-z0-9-]+", text.lower())
    if not MIN_WORDS <= len(words) <= MAX_WORDS:
        raise ValueError(f"Предсказание должно содержать от {MIN_WORDS} до {MAX_WORDS} слов.")

    normalized = normalize_prediction_text(text)
    if any(fragment in normalized for fragment in PROHIBITED_TOPICS):
        raise ValueError("Предсказание затрагивает запрещённую серьёзную тему.")
    if any(template in normalized for template in PROHIBITED_TEMPLATES):
        raise ValueError("Предсказание использует слишком шаблонную формулировку.")

    for existing in existing_texts:
        if normalized == normalize_prediction_text(existing):
            raise ValueError("Такое предсказание уже существует.")
        if prediction_similarity(text, existing) >= SIMILARITY_THRESHOLD:
            raise ValueError("Предсказание слишком похоже на существующее.")

    return text


class FortuneCookieGenerator:
    """Генерирует предсказания по воспроизводимому набору творческих признаков."""

    def __init__(self):
        self.model = os.getenv("GIGACHAT_MODEL", DEFAULT_GIGACHAT_MODEL).strip() or DEFAULT_GIGACHAT_MODEL
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
            self.config_error = "Пакет gigachat не установлен. Установите зависимости из requirements.txt."
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
            attempts = int(os.getenv("COOKIE_GENERATION_ATTEMPTS", "4"))
        except ValueError:
            return 4
        return max(1, attempts)

    def ensure_ready(self) -> None:
        if self.config_error:
            raise FortuneCookieConfigError(self.config_error)
        if not self.client:
            raise FortuneCookieConfigError("GigaChat-клиент не инициализирован.")

    def _build_prompt(
        self,
        recipe: FortuneCookieRecipe,
        forbidden_texts: tuple[str, ...],
    ):
        rarity_descriptions = {
            "common": "бытовое, узнаваемое и забавное",
            "uncommon": "необычное, с комичным совпадением или абсурдным поворотом",
            "rare": "яркое, неожиданное и с хорошим панчлайном",
            "legendary": "эпически абсурдное и торжественно-смешное, но доброжелательное",
        }
        forbidden_block = "\n".join(
            f"{index}. {text}"
            for index, text in enumerate(forbidden_texts[-12:], start=1)
        ) or "Нет."

        system_prompt = (
            "Ты создаёшь короткие предсказания для печенья в русскоязычном Discord-боте. "
            "Главная цель — вызвать улыбку: предсказание должно быть живым, конкретным, "
            "забавным и доброжелательным. Используй бытовой абсурд, самоиронию, неожиданное "
            "сравнение или короткий панчлайн. Не превращай текст в скучный мотивирующий совет. "
            "Допустимы безобидные неловкости и мелкие смешные неудачи, но не унижай человека, "
            "не оскорбляй его внешность или ум и не используй грубый мат. "
            "Используй карты Таро только как метафорические архетипы, а не как буквальное гадание. "
            "Аркан Смерть означает перемены и завершение этапа, а не физическую смерть. "
            "Не давай категоричных обещаний и не затрагивай смерть, болезни, несчастья, беременность, "
            "расставание, крупные деньги и другие серьёзные события. "
            "Не начинай с формул 'тебя ждёт', 'судьба приготовила' и 'скоро произойдёт'. "
            "Обращайся на 'ты', не называй параметры задания и не объясняй ответ. "
            "Верни только JSON вида {\"prediction\":\"текст\"}."
        )
        user_prompt = (
            f"Идентификатор варианта: {recipe.seed}\n"
            f"Редкость: {rarity_descriptions[recipe.rarity]}.\n"
            f"Тема: {recipe.theme}.\n"
            f"Ситуация: {recipe.setting}.\n"
            f"Настроение: {recipe.tone}.\n"
            f"Срок: {recipe.time_horizon}.\n"
            f"Дополнительный образ: {recipe.image}.\n"
            f"Аркан Таро: {recipe.arcana}.\n"
            f"Композиция: {recipe.structure}.\n"
            f"Длина: от {MIN_WORDS} до {MAX_WORDS} слов, одна строка.\n"
            "Возьми традиционный символический смысл аркана за основу предсказания, но не обязан "
            "называть карту в тексте. Дополнительный образ используй буквально или метафорически. "
            "Добавь одну конкретную смешную деталь и неожиданный поворот ближе к концу. "
            "Не копируй и не перефразируй "
            f"запрещённые варианты:\n{forbidden_block}"
        )
        return self.chat_payload_class(
            model=self.model,
            messages=[
                self.message_class(role=self.role_class.SYSTEM, content=system_prompt),
                self.message_class(role=self.role_class.USER, content=user_prompt),
            ],
            max_tokens=192,
            response_format={
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {"prediction": {"type": "string"}},
                    "required": ["prediction"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        )

    def _request_prediction(
        self,
        recipe: FortuneCookieRecipe,
        forbidden_texts: tuple[str, ...],
    ):
        return self.client.chat(self._build_prompt(recipe, forbidden_texts))

    async def _request_prediction_with_limit(
        self,
        recipe: FortuneCookieRecipe,
        forbidden_texts: tuple[str, ...],
    ):
        async with _GIGACHAT_REQUEST_SEMAPHORE:
            return await asyncio.to_thread(self._request_prediction, recipe, forbidden_texts)

    async def generate_prediction(
        self,
        recipe: FortuneCookieRecipe,
        existing_texts: tuple[str, ...] = (),
    ) -> dict:
        self.ensure_ready()
        rejected_texts: tuple[str, ...] = ()
        last_error = None

        for _ in range(self.attempts):
            forbidden_texts = tuple(dict.fromkeys((*existing_texts, *rejected_texts)))
            try:
                response = await self._request_prediction_with_limit(recipe, forbidden_texts)
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

            try:
                payload = _extract_json_payload(output_text)
                raw_prediction = payload.get("prediction", "")
            except (json.JSONDecodeError, AttributeError):
                raw_prediction = output_text

            try:
                prediction = validate_prediction_text(raw_prediction, existing_texts)
            except ValueError as error:
                normalized_candidate = normalize_prediction_text(raw_prediction)
                if normalized_candidate:
                    rejected_texts = rejected_texts + (raw_prediction,)
                last_error = FortuneCookieGenerationError(str(error))
                continue

            result = asdict(recipe)
            result.update(
                {
                    "text": prediction,
                    "normalized_text": normalize_prediction_text(prediction),
                    "generation_model": self.model,
                    "style_version": COOKIE_STYLE_VERSION,
                }
            )
            result.pop("structure")
            return result

        raise last_error or FortuneCookieGenerationError(
            "GigaChat не смог создать достаточно уникальное предсказание."
        )
