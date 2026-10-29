import random
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.modules.fortune_cookie_service import (
    COOKIE_STYLE_VERSION,
    FortuneCookieGenerator,
    IMAGES,
    MAJOR_ARCANA,
    MINOR_ARCANA,
    RARITY_WEIGHTS,
    TAROT_ARCANA,
    build_fortune_cookie_recipe,
    choose_rarity,
    normalize_prediction_text,
    prediction_similarity,
    validate_prediction_text,
)


class FortuneCookieServiceTests(unittest.TestCase):
    def test_tarot_deck_contains_all_unique_arcana(self):
        self.assertEqual(len(MAJOR_ARCANA), 22)
        self.assertEqual(len(MINOR_ARCANA), 56)
        self.assertEqual(len(TAROT_ARCANA), 78)
        self.assertEqual(len(set(TAROT_ARCANA)), 78)

    def test_image_dictionary_has_at_least_one_hundred_unique_values(self):
        self.assertGreaterEqual(len(IMAGES), 100)
        self.assertEqual(len(IMAGES), len(set(IMAGES)))

    def test_recipe_is_stable_for_same_seed(self):
        first = build_fortune_cookie_recipe(123456, "rare")
        second = build_fortune_cookie_recipe(123456, "rare")

        self.assertEqual(first, second)
        self.assertIn(first.arcana, TAROT_ARCANA)

    def test_recipe_changes_for_another_seed(self):
        first = build_fortune_cookie_recipe(1, "common")
        second = build_fortune_cookie_recipe(2, "common")

        self.assertNotEqual(first, second)

    def test_rarity_always_comes_from_supported_values(self):
        rng = random.Random(42)

        rarities = {choose_rarity(rng) for _ in range(100)}

        self.assertTrue(rarities)
        self.assertTrue(rarities.issubset(RARITY_WEIGHTS))

    def test_normalization_ignores_case_and_punctuation(self):
        normalized = normalize_prediction_text("  Ключ, Откроет новое ОКНО! ")

        self.assertEqual(normalized, "ключ откроет новое окно")

    def test_validation_accepts_safe_prediction(self):
        text = "Сегодня знакомый разговор поможет заметить полезную возможность совсем рядом."

        self.assertEqual(validate_prediction_text(text), text)

    def test_validation_rejects_template_phrase(self):
        text = "Сегодня тебя ждёт удивительная встреча, которая мягко изменит привычный маршрут."

        with self.assertRaisesRegex(ValueError, "шаблонную"):
            validate_prediction_text(text)

    def test_validation_rejects_generic_fortune_teller_phrase(self):
        text = "Судьба распорядилась так, что сегодня твой тапок внезапно станет главным советчиком."

        with self.assertRaisesRegex(ValueError, "шаблонную"):
            validate_prediction_text(text)

    def test_validation_rejects_lexically_similar_prediction(self):
        existing = "Обычный разговор поможет тебе заметить полезную возможность совсем рядом."
        candidate = "Обычный разговор поможет тебе увидеть полезную возможность совсем рядом."

        self.assertGreaterEqual(prediction_similarity(existing, candidate), 0.72)
        with self.assertRaisesRegex(ValueError, "похоже"):
            validate_prediction_text(candidate, (existing,))


class FortuneCookieGeneratorTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _response(text: str):
        message = SimpleNamespace(content=text)
        choice = SimpleNamespace(message=message, finish_reason="stop")
        return SimpleNamespace(choices=[choice], id="test-response", model="test-model")

    async def test_generator_retries_after_similar_prediction(self):
        existing = "Обычный разговор поможет тебе заметить полезную возможность совсем рядом."
        similar = "Обычный разговор поможет тебе увидеть полезную возможность совсем рядом."
        unique = "Забытый рисунок неожиданно подскажет простой способ оживить твою новую идею."
        generator = FortuneCookieGenerator.__new__(FortuneCookieGenerator)
        generator.model = "test-model"
        generator.attempts = 2
        generator.config_error = None
        generator.client = object()
        generator._request_prediction_with_limit = AsyncMock(
            side_effect=[
                self._response(f'{{"prediction":"{similar}"}}'),
                self._response(f'{{"prediction":"{unique}"}}'),
            ]
        )
        recipe = build_fortune_cookie_recipe(321, "uncommon")

        result = await generator.generate_prediction(recipe, (existing,))

        self.assertEqual(result["text"], unique)
        self.assertEqual(result["seed"], 321)
        self.assertEqual(result["arcana"], recipe.arcana)
        self.assertEqual(result["style_version"], COOKIE_STYLE_VERSION)
        self.assertEqual(generator._request_prediction_with_limit.await_count, 2)


if __name__ == "__main__":
    unittest.main()
