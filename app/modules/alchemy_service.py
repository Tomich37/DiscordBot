import json
import os
import re
import asyncio

from dotenv import load_dotenv


load_dotenv()


DEFAULT_GIGACHAT_MODEL = "GigaChat"


def _read_positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


# GigaChat в текущем тарифе принимает один одновременный запрос, поэтому
# все генерации рецептов проходят через общий семафор и ждут своей очереди.
GIGACHAT_MAX_CONCURRENT_REQUESTS = _read_positive_int_env("GIGACHAT_MAX_CONCURRENT_REQUESTS", 1)
_GIGACHAT_REQUEST_SEMAPHORE = asyncio.Semaphore(GIGACHAT_MAX_CONCURRENT_REQUESTS)
GIGACHAT_GENERATION_ATTEMPTS = _read_positive_int_env("GIGACHAT_GENERATION_ATTEMPTS", 3)


class AlchemyConfigError(Exception):
    pass


class AlchemyGenerationError(Exception):
    pass


def normalize_alchemy_word(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_alchemy_pair(left_word: str, right_word: str) -> tuple[str, str]:
    left = normalize_alchemy_word(left_word)
    right = normalize_alchemy_word(right_word)
    return tuple(sorted((left, right)))


def validate_alchemy_word(value: str) -> str:
    normalized = normalize_alchemy_word(value)
    if not normalized:
        raise ValueError("Результат пустой.")
    if len(normalized) > 40:
        raise ValueError("Результат слишком длинный.")
    if " " in normalized:
        raise ValueError("Результат должен быть одним словом.")
    if not re.fullmatch(r"[а-яё-]+", normalized):
        raise ValueError("Результат должен быть русским словом.")

    return normalized


def validate_alchemy_result(value: str, left_word: str, right_word: str) -> str:
    result = validate_alchemy_word(value)
    if result == left_word or result == right_word:
        raise ValueError("Результат не должен совпадать с исходными элементами.")
    return result


def _extract_response_text(response) -> str:
    choices = getattr(response, "choices", []) or []
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    if not message and isinstance(choices[0], dict):
        message = choices[0].get("message")

    if isinstance(message, dict):
        return (message.get("content") or "").strip()

    return (getattr(message, "content", "") or "").strip()


def _extract_json_payload(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def _extract_plain_result(text: str) -> str:
    return text.strip().strip("\"'`«»").rstrip(".").strip()


def _describe_empty_response(response) -> str:
    details = []
    model = getattr(response, "model", None)
    usage = getattr(response, "usage", None)
    finish_reason = None

    choices = getattr(response, "choices", []) or []
    if choices:
        finish_reason = getattr(choices[0], "finish_reason", None)
        if finish_reason is None and isinstance(choices[0], dict):
            finish_reason = choices[0].get("finish_reason")

    if model:
        details.append(f"model={model}")
    if finish_reason:
        details.append(f"finish_reason={finish_reason}")
    if usage:
        details.append(f"usage={usage}")

    return ", ".join(details) if details else "без деталей ответа"


class AlchemyGenerator:
    def __init__(self):
        self.model = os.getenv("GIGACHAT_MODEL", DEFAULT_GIGACHAT_MODEL).strip() or DEFAULT_GIGACHAT_MODEL
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

        verify_ssl_certs = os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "false").lower() not in {"0", "false", "no", "off"}
        self.client = GigaChat(credentials=api_key, verify_ssl_certs=verify_ssl_certs)
        self.chat_payload_class = Chat
        self.message_class = Messages
        self.role_class = MessagesRole

    def ensure_ready(self):
        if self.config_error:
            raise AlchemyConfigError(self.config_error)
        if not self.client:
            raise AlchemyConfigError("GigaChat-клиент не инициализирован.")

    def _build_prompt(self, left_word: str, right_word: str, rejected_results: tuple[str, ...] = ()):
        rejected_results_text = ""
        if rejected_results:
            rejected_results_text = (
                "\nЗапрещённые варианты результата: "
                + ", ".join(rejected_results)
                + "."
            )

        system_prompt = (
            "Ты движок мини-игры 'Алхимия' для русскоязычного Discord-сервера. "
            "По двум элементам придумай один логичный результат. "
            "Верни только JSON вида {\"result\":\"слово\"}. Значение result должно быть одним русским существительным, "
            "без пояснений, эмодзи, кавычек внутри слова и лишних слов. "
            "Результат не должен совпадать ни с первым, ни со вторым исходным элементом."
        )
        user_prompt = (
            f"Элемент 1: {left_word}\n"
            f"Элемент 2: {right_word}\n"
            "Нужен результат сочетания."
            f"{rejected_results_text}"
        )
        return self.chat_payload_class(
            model=self.model,
            messages=[
                self.message_class(role=self.role_class.SYSTEM, content=system_prompt),
                self.message_class(role=self.role_class.USER, content=user_prompt),
            ],
            max_tokens=256,
            response_format={
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "result": {
                            "type": "string",
                            "description": "Одно русское слово - результат сочетания элементов.",
                        }
                    },
                    "required": ["result"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        )

    def _request_result(self, left_word: str, right_word: str, rejected_results: tuple[str, ...] = ()):
        return self.client.chat(self._build_prompt(left_word, right_word, rejected_results))

    async def _request_result_with_limit(
        self,
        left_word: str,
        right_word: str,
        rejected_results: tuple[str, ...] = (),
    ):
        async with _GIGACHAT_REQUEST_SEMAPHORE:
            return await asyncio.to_thread(self._request_result, left_word, right_word, rejected_results)

    async def generate_result(self, left_word: str, right_word: str) -> dict:
        self.ensure_ready()

        rejected_results = (left_word, right_word)
        last_error = None

        for _ in range(GIGACHAT_GENERATION_ATTEMPTS):
            response = await self._request_result_with_limit(left_word, right_word, rejected_results)

            output_text = _extract_response_text(response)
            if not output_text:
                details = _describe_empty_response(response)
                last_error = AlchemyGenerationError(f"GigaChat вернул пустой ответ: {details}.")
                continue

            try:
                payload = _extract_json_payload(output_text)
                raw_result = payload.get("result", "")
            except json.JSONDecodeError:
                raw_result = _extract_plain_result(output_text)

            try:
                result = validate_alchemy_result(raw_result, left_word, right_word)
            except ValueError as error:
                normalized_candidate = normalize_alchemy_word(raw_result)
                if normalized_candidate and normalized_candidate not in rejected_results:
                    rejected_results = rejected_results + (normalized_candidate,)
                last_error = AlchemyGenerationError(str(error))
                continue

            return {
                "result_normalized": result,
                "result_display": result,
                "response_id": getattr(response, "id", None),
                "model": self.model,
            }

        raise last_error or AlchemyGenerationError("GigaChat не смог подобрать подходящий результат.")
