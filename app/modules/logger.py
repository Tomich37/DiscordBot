import os
import logging
import sys
from datetime import date, datetime, timedelta


def fix_text_mojibake(text: str) -> str:
    if not isinstance(text, str):
        return text

    fixed = _decode_mojibake_variant(text, "cp874")
    if fixed != text:
        return fixed

    return _decode_mojibake_variant(text, "cp1251")


def _decode_mojibake_variant(text: str, encoding: str) -> str:
    try:
        raw_bytes = _encode_mojibake_bytes(text, encoding)
        fixed = raw_bytes.decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

    return fixed if _mojibake_score(fixed) < _mojibake_score(text) else text


def _encode_mojibake_bytes(text: str, encoding: str) -> bytes:
    chunks = bytearray()
    for char in text:
        codepoint = ord(char)
        if 0x80 <= codepoint <= 0x9F:
            chunks.append(codepoint)
            continue

        chunks.extend(char.encode(encoding))

    return bytes(chunks)


def _mojibake_score(text: str) -> int:
    # Чем больше в строке служебных и тайских символов, тем вероятнее сломанная UTF-8 строка.
    cp1251_fragments = ("Рќ", "Рµ", "С…", "Р°", "Рё", "Рѕ", "СЃ", "С‚", "СЊ", "Р»")
    cp1251_mojibake = sum(text.count(fragment) for fragment in cp1251_fragments)
    thai_chars = sum("\u0e00" <= char <= "\u0e7f" for char in text)
    c1_controls = sum("\u0080" <= char <= "\u009f" for char in text)
    replacement_chars = text.count("\ufffd")
    cyrillic_chars = sum("\u0400" <= char <= "\u04ff" for char in text)
    return thai_chars * 3 + c1_controls * 4 + replacement_chars * 5 + cp1251_mojibake * 3 - cyrillic_chars


class Utf8SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_msg = record.msg
        original_args = record.args

        try:
            record.msg = fix_text_mojibake(record.getMessage())
            record.args = ()
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


class LevelFilter(logging.Filter):
    def __init__(self, allowed_levels: set[int]) -> None:
        super().__init__()
        self.allowed_levels = allowed_levels

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno in self.allowed_levels


class DailyFileHandler(logging.Handler):
    def __init__(self, logs_dir: str, file_prefix: str, backup_days: int = 30) -> None:
        super().__init__()
        self.logs_dir = logs_dir
        self.file_prefix = file_prefix
        self.backup_days = backup_days
        self.current_date = None
        self.stream = None
        self._open_current_file()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.current_date != date.today():
                self._open_current_file()

            message = self.format(record)
            self.stream.write(f"{message}\n")
            self.flush()
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        if self.stream:
            self.stream.flush()

    def close(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None
        super().close()

    def _open_current_file(self) -> None:
        if self.stream:
            self.stream.close()

        self.current_date = date.today()
        log_file = os.path.join(
            self.logs_dir,
            f"{self.file_prefix}_{self.current_date:%Y-%m-%d}.log",
        )
        self.stream = open(log_file, "a", encoding="utf-8")
        self._delete_old_logs()

    def _delete_old_logs(self) -> None:
        if self.backup_days <= 0:
            return

        min_date = date.today() - timedelta(days=self.backup_days)
        for file_name in os.listdir(self.logs_dir):
            if not file_name.startswith(f"{self.file_prefix}_") or not file_name.endswith(".log"):
                continue

            date_text = file_name.removeprefix(f"{self.file_prefix}_").removesuffix(".log")
            try:
                file_date = datetime.strptime(date_text, "%Y-%m-%d").date()
            except ValueError:
                continue

            if file_date < min_date:
                os.remove(os.path.join(self.logs_dir, file_name))


class SetLogs:
    def __init__(self) -> None:
        # Логи делим по назначению и по дням, чтобы проще искать пользовательские и технические события.
        logs_dir = os.getenv(
            "LOGS_DIR",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"),
        )
        os.makedirs(logs_dir, exist_ok=True)
        debug_enabled = os.getenv("DEBUG_LOGS", "").lower() in {"1", "true", "yes", "on"}
        technical_levels = {logging.WARNING, logging.ERROR, logging.CRITICAL}
        if debug_enabled:
            technical_levels.add(logging.DEBUG)

        log_format = "%(asctime)s - %(levelname)s - %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"

        formatter = Utf8SafeFormatter(log_format, datefmt=date_format)
        self.logger = logging.getLogger("discord_bot")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        # Защита от дублей при повторной инициализации в тестах или reload.
        if self.logger.handlers:
            self.logger.handlers.clear()

        info_handler = DailyFileHandler(logs_dir, "info", backup_days=30)
        info_handler.setLevel(logging.INFO)
        info_handler.addFilter(LevelFilter({logging.INFO}))
        info_handler.setFormatter(formatter)

        technical_handler = DailyFileHandler(logs_dir, "technical", backup_days=30)
        technical_handler.setLevel(logging.DEBUG)
        technical_handler.addFilter(LevelFilter(technical_levels))
        technical_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(info_handler)
        self.logger.addHandler(technical_handler)
        self.logger.addHandler(console_handler)

        # Voice-подключение и ffmpeg живут внутри disnake, поэтому отдельно пишем их debug в technical.
        for logger_name in ("disnake.voice_client", "disnake.player", "disnake.gateway"):
            external_logger = logging.getLogger(logger_name)
            external_logger.setLevel(logging.DEBUG if debug_enabled else logging.WARNING)
            external_logger.propagate = False
            external_logger.handlers.clear()
            external_logger.addHandler(technical_handler)
            external_logger.addHandler(console_handler)
