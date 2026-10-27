import io
import logging
import unittest

from app.modules.logger import Utf8SafeFormatter, configure_utf8_stream, fix_text_mojibake


class LoggerEncodingTests(unittest.TestCase):
    def test_correct_russian_text_is_not_changed(self):
        text = (
            "Слеш-команда | пользователь: Тест | команда: /cookie | параметры: нет"
        )

        self.assertEqual(fix_text_mojibake(text), text)

    def test_console_stream_is_reconfigured_to_utf8(self):
        raw_stream = io.BytesIO()
        text_stream = io.TextIOWrapper(raw_stream, encoding="cp1251")

        configured_stream = configure_utf8_stream(text_stream)
        configured_stream.write("Печенье открыто")
        configured_stream.flush()

        self.assertEqual(configured_stream.encoding.lower(), "utf-8")
        self.assertEqual(raw_stream.getvalue().decode("utf-8"), "Печенье открыто")

    def test_formatter_keeps_russian_log_message(self):
        formatter = Utf8SafeFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Печенье открыто",
            args=(),
            exc_info=None,
        )

        self.assertEqual(formatter.format(record), "INFO - Печенье открыто")


if __name__ == "__main__":
    unittest.main()
