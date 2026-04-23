import os
import logging
from datetime import date, datetime, timedelta


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
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        log_format = "%(asctime)s - %(levelname)s - %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"

        formatter = logging.Formatter(log_format, datefmt=date_format)
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
        technical_handler.addFilter(
            LevelFilter({
                logging.DEBUG,
                logging.WARNING,
                logging.ERROR,
                logging.CRITICAL,
            })
        )
        technical_handler.setFormatter(formatter)

        self.logger.addHandler(info_handler)
        self.logger.addHandler(technical_handler)
