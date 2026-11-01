"""Создаёт статический словарь тем для печенья из частотной русской лексики.

Скрипт нужен только для обновления файла данных. Работающий бот не зависит от
wordfreq и pymorphy3.
"""

import re
from pathlib import Path

import pymorphy3
from wordfreq import top_n_list


WORD_COUNT = 10_000
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "app"
    / "data"
    / "fortune_cookie_words.txt"
)
RUSSIAN_WORD_PATTERN = re.compile(r"[а-яё]{3,20}")
EXCLUDED_GRAMMEMES = {"Name", "Surn", "Patr", "Geox", "Orgn", "Abbr"}
EXCLUDED_WORDS = {
    "блядь",
    "говно",
    "долбоёб",
    "еблан",
    "мудак",
    "пизда",
    "сука",
    "хуй",
}


def build_words() -> list[str]:
    """Возвращает 10 000 частотных существительных в нормальной форме."""

    morph = pymorphy3.MorphAnalyzer()
    words: list[str] = []
    seen: set[str] = set()

    for source_word in top_n_list("ru", 300_000):
        if not RUSSIAN_WORD_PATTERN.fullmatch(source_word):
            continue

        parsed = morph.parse(source_word)[0]
        if not parsed.is_known or parsed.tag.POS != "NOUN":
            continue
        if set(parsed.tag.grammemes) & EXCLUDED_GRAMMEMES:
            continue

        word = parsed.normal_form
        if not RUSSIAN_WORD_PATTERN.fullmatch(word):
            continue
        if word in seen or word in EXCLUDED_WORDS or "эфир" in word:
            continue

        seen.add(word)
        words.append(word)
        if len(words) == WORD_COUNT:
            return words

    raise RuntimeError(f"Удалось собрать только {len(words)} слов из {WORD_COUNT}.")


def main() -> None:
    """Записывает готовый словарь в UTF-8, по одному слову на строку."""

    words = build_words()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(words) + "\n", encoding="utf-8")
    print(f"Записано слов: {len(words)}; файл: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
