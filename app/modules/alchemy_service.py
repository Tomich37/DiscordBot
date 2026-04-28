import json
import os
import re

from dotenv import load_dotenv
from openai import AsyncOpenAI


load_dotenv()


ALLOWED_ALCHEMY_MODELS = {"gpt-5-nano", "gpt-5.4-nano", "gpt-5.4-mini"}


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


def _extract_response_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    parts = []
    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            text = getattr(content_item, "text", None)
            if text:
                parts.append(text)
            elif isinstance(content_item, dict) and content_item.get("text"):
                parts.append(content_item["text"])

    return "".join(parts).strip()


def _describe_empty_response(response) -> str:
    status = getattr(response, "status", None)
    incomplete_details = getattr(response, "incomplete_details", None)
    output_types = [
        getattr(output_item, "type", type(output_item).__name__)
        for output_item in getattr(response, "output", []) or []
    ]

    details = []
    if status:
        details.append(f"status={status}")
    if incomplete_details:
        details.append(f"incomplete_details={incomplete_details}")
    if output_types:
        details.append(f"output_types={output_types}")

    return ", ".join(details) if details else "без деталей ответа"


class AlchemyGenerator:
    def __init__(self):
        self.model = os.getenv("ALCHEMY_MODEL", "gpt-5-nano").strip()
        self.config_error = None
        self.client = None

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.config_error = "OPENAI_API_KEY не задан в .env."
            return

        if self.model not in ALLOWED_ALCHEMY_MODELS:
            allowed_models = ", ".join(sorted(ALLOWED_ALCHEMY_MODELS))
            self.config_error = f"ALCHEMY_MODEL должен быть одним из: {allowed_models}."
            return

        self.client = AsyncOpenAI(api_key=api_key)

    def ensure_ready(self):
        if self.config_error:
            raise AlchemyConfigError(self.config_error)
        if not self.client:
            raise AlchemyConfigError("OpenAI-клиент не инициализирован.")

    async def generate_result(self, left_word: str, right_word: str) -> dict:
        self.ensure_ready()

        response = await self.client.responses.create(
            model=self.model,
            instructions=(
                "Ты движок мини-игры 'Алхимия' для русскоязычного Discord-сервера. "
                "По двум элементам придумай один логичный результат. "
                "Верни только JSON по схеме. Значение result должно быть одним русским существительным, "
                "без пояснений, эмодзи, кавычек внутри слова и лишних слов."
            ),
            input=(
                f"Элемент 1: {left_word}\n"
                f"Элемент 2: {right_word}\n"
                "Нужен результат сочетания."
            ),
            max_output_tokens=256,
            reasoning={"effort": "minimal"},
            store=False,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "alchemy_result",
                    "strict": True,
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
                }
            },
        )

        output_text = _extract_response_text(response)
        if not output_text:
            details = _describe_empty_response(response)
            raise AlchemyGenerationError(f"OpenAI вернул пустой ответ: {details}.")

        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as error:
            raise AlchemyGenerationError("OpenAI вернул невалидный JSON.") from error

        try:
            result = validate_alchemy_word(payload.get("result", ""))
        except ValueError as error:
            raise AlchemyGenerationError(str(error)) from error

        return {
            "result_normalized": result,
            "result_display": result,
            "response_id": getattr(response, "id", None),
            "model": self.model,
        }
