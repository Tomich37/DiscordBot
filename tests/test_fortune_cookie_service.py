import json
import random
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.modules.fortune_cookie_service import (
    ALLOWED_HORIZONS,
    COOKIE_STYLE_VERSION,
    RARITY_DIRECTIONS,
    RARITY_WEIGHTS,
    FortuneCookieGenerator,
    build_fortune_cookie_recipe,
    choose_rarity,
    normalize_prediction_text,
    prediction_similarity,
    validate_prediction_bundle,
    validate_prediction_text,
    validate_theme_word,
)


class FortuneCookieServiceTests(unittest.TestCase):
    def test_recipe_contains_only_seed_and_rarity(self):
        recipe = build_fortune_cookie_recipe(123456, "rare")

        self.assertEqual(recipe.seed, 123456)
        self.assertEqual(recipe.rarity, "rare")
        self.assertEqual(recipe.__slots__, ("seed", "rarity"))

    def test_recipe_rejects_unknown_rarity(self):
        with self.assertRaisesRegex(ValueError, "Неизвестная редкость"):
            build_fortune_cookie_recipe(1, "mythical")

    def test_rarity_always_comes_from_supported_values(self):
        rng = random.Random(42)
        rarities = {choose_rarity(rng) for _ in range(100)}

        self.assertTrue(rarities)
        self.assertTrue(rarities.issubset(RARITY_WEIGHTS))
        self.assertEqual(set(RARITY_WEIGHTS), set(RARITY_DIRECTIONS))

    def test_theme_validation_accepts_one_russian_word(self):
        self.assertEqual(validate_theme_word("  Маяк  "), "маяк")
        self.assertEqual(validate_theme_word("эхо-камера"), "эхо-камера")

    def test_theme_validation_rejects_phrase_and_unsafe_word(self):
        with self.assertRaisesRegex(ValueError, "одного русского слова"):
            validate_theme_word("старый маяк")
        with self.assertRaisesRegex(ValueError, "небезопасное"):
            validate_theme_word("катастрофа")

    def test_first_prompt_only_requests_a_free_word(self):
        generator = self._prompt_generator()

        payload = generator._build_theme_prompt(777)
        prompt = " ".join(message.content for message in payload.messages)

        self.assertIn("одно случайное существующее русское", prompt)
        self.assertIn("любое новое выразительное слово", prompt)
        self.assertIn('"слово"', json.dumps(payload.response_format, ensure_ascii=False))
        self.assertNotIn("предсказание должно содержать", prompt.lower())

    def test_second_prompt_gives_model_freedom_to_interpret_theme(self):
        generator = self._prompt_generator()
        recipe = build_fortune_cookie_recipe(777, "rare")

        payload = generator._build_prompt(recipe, "маяк", ())
        system_prompt = payload.messages[0].content
        user_prompt = payload.messages[1].content

        self.assertIn("Свободная тема: «маяк»", user_prompt)
        self.assertIn("Полностью самостоятельно придумай", user_prompt)
        self.assertIn("не обязан использовать его буквально", system_prompt)
        self.assertIn('"предсказание"', json.dumps(payload.response_format, ensure_ascii=False))
        self.assertNotIn("Аркан Таро", user_prompt)

    @staticmethod
    def _prompt_generator():
        generator = FortuneCookieGenerator.__new__(FortuneCookieGenerator)
        generator.model = "test-model"
        generator.chat_payload_class = lambda **kwargs: SimpleNamespace(**kwargs)
        generator.message_class = lambda **kwargs: SimpleNamespace(**kwargs)
        generator.role_class = SimpleNamespace(SYSTEM="system", USER="user")
        return generator

    def test_normalization_ignores_case_and_punctuation(self):
        self.assertEqual(
            normalize_prediction_text("  Ключ, Откроет новое ОКНО! "),
            "ключ откроет новое окно",
        )

    def test_validation_accepts_concrete_future_scene(self):
        text = (
            "Знакомый разговор до конца дня поможет прояснить старый вопрос, "
            "когда собеседник сам упомянет деталь, о которой ты хотел спросить."
        )

        self.assertEqual(validate_prediction_text(text), text)

    def test_validation_rejects_fortune_teller_cliche(self):
        text = (
            "Судьба приготовила тебе приятный сюрприз, и до конца дня случайная "
            "встреча обязательно поможет наконец найти правильный ответ."
        )

        with self.assertRaisesRegex(ValueError, "шаблонную"):
            validate_prediction_text(text)

    def test_validation_rejects_object_as_magical_adviser(self):
        text = (
            "Утром придётся выбирать между двумя встречами, а оставленная на столе "
            "тарелка привлечёт внимание в нужный момент — она подскажет правильный ответ."
        )

        with self.assertRaisesRegex(ValueError, "шаблонную"):
            validate_prediction_text(text)

    def test_validation_rejects_caption_without_future_event(self):
        text = (
            "Старый вопрос оказался проще, чем выглядел, а короткий разговор "
            "уже расставил все детали на свои места без лишнего шума."
        )

        with self.assertRaisesRegex(ValueError, "не описывает будущее"):
            validate_prediction_text(text)

    def test_bundle_rejects_empty_advice(self):
        prediction = (
            "Знакомый разговор до конца дня поможет прояснить старый вопрос, "
            "когда собеседник сам упомянет деталь, о которой ты хотел спросить."
        )

        with self.assertRaisesRegex(ValueError, "слишком общей"):
            validate_prediction_bundle(
                "Разговор без репетиции",
                prediction,
                "Просто верь в себя",
                "до конца дня",
            )

    def test_validation_rejects_lexically_similar_prediction(self):
        existing = (
            "Короткий разговор до конца дня поможет прояснить старый вопрос, "
            "когда собеседник сам назовёт деталь, о которой ты хотел спросить."
        )
        candidate = (
            "Короткий разговор до конца дня поможет прояснить старый вопрос, "
            "когда собеседник сам упомянет деталь, о которой ты хотел спросить."
        )

        self.assertGreaterEqual(prediction_similarity(existing, candidate), 0.68)
        with self.assertRaisesRegex(ValueError, "похоже"):
            validate_prediction_text(candidate, (existing,))


class FortuneCookieGeneratorTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _response(payload: dict):
        message = SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
        choice = SimpleNamespace(message=message, finish_reason="stop")
        return SimpleNamespace(choices=[choice], id="test-response", model="test-model")

    async def test_generator_makes_theme_request_before_prediction_request(self):
        prediction = (
            "Незнакомый маршрут к вечеру окажется короче привычного, когда яркая "
            "вывеска поможет заметить тихий двор и удобный проход через него."
        )
        generator = FortuneCookieGenerator.__new__(FortuneCookieGenerator)
        generator.model = "test-model"
        generator.attempts = 2
        generator.config_error = None
        generator.client = object()
        call_order = []

        async def request_theme(seed):
            call_order.append(("theme", seed))
            return self._response({"theme": "маяк"})

        async def request_prediction(*args):
            call_order.append(("prediction", args[1]))
            return self._response(
                {
                    "title": "Свет на другом маршруте",
                    "prediction": prediction,
                    "advice": "Сверни один раз с привычного пути и осмотрись.",
                    "horizon": "до конца дня",
                }
            )

        generator._request_theme_with_limit = AsyncMock(side_effect=request_theme)
        generator._request_prediction_with_limit = AsyncMock(
            side_effect=request_prediction
        )
        recipe = build_fortune_cookie_recipe(321, "uncommon")

        result = await generator.generate_prediction(recipe)

        self.assertEqual(call_order, [("theme", 321), ("prediction", "маяк")])
        self.assertEqual(result["theme"], "Маяк")
        self.assertEqual(result["title"], "Свет на другом маршруте")
        self.assertEqual(result["text"], prediction)
        self.assertEqual(result["time_horizon"], "до конца дня")
        self.assertEqual(result["style_version"], COOKIE_STYLE_VERSION)
        self.assertIsNone(result["arcana"])

    async def test_generator_retries_only_second_stage_after_similar_text(self):
        existing = (
            "Короткий разговор до конца дня поможет прояснить старый вопрос, "
            "когда собеседник сам назовёт деталь, о которой ты хотел спросить."
        )
        similar = (
            "Короткий разговор до конца дня поможет прояснить старый вопрос, "
            "когда собеседник сам упомянет деталь, о которой ты хотел спросить."
        )
        unique = (
            "Незаконченный черновик к вечеру окажется лучше, чем ты помнил: "
            "одна точная правка превратит его в идею, которой уже можно поделиться."
        )
        generator = FortuneCookieGenerator.__new__(FortuneCookieGenerator)
        generator.model = "test-model"
        generator.attempts = 2
        generator.config_error = None
        generator.client = object()
        generator._request_theme_with_limit = AsyncMock(
            return_value=self._response({"theme": "черновик"})
        )
        generator._request_prediction_with_limit = AsyncMock(
            side_effect=[
                self._response(
                    {
                        "title": "Разговор без репетиции",
                        "prediction": similar,
                        "advice": "Задай один прямой вопрос без длинного вступления.",
                        "horizon": "до конца дня",
                    }
                ),
                self._response(
                    {
                        "title": "Черновик уже созрел",
                        "prediction": unique,
                        "advice": "Исправь одну заметную деталь и покажи результат кому-нибудь.",
                        "horizon": "в ближайшие два дня",
                    }
                ),
            ]
        )

        result = await generator.generate_prediction(
            build_fortune_cookie_recipe(321, "uncommon"),
            (existing,),
        )

        self.assertEqual(result["text"], unique)
        self.assertEqual(generator._request_theme_with_limit.await_count, 1)
        self.assertEqual(generator._request_prediction_with_limit.await_count, 2)
        rejection_notes = generator._request_prediction_with_limit.await_args_list[1].args[3]
        self.assertTrue(rejection_notes)
        self.assertIn(result["time_horizon"], ALLOWED_HORIZONS)


if __name__ == "__main__":
    unittest.main()
