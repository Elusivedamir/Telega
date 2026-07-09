import logging
import os
import platform
import random
from logging.handlers import RotatingFileHandler

import config

APP_NAME = "TelegramAutoBot"


def get_app_dir():
    return config.get_app_dir()


def setup_macos_optimizations():
    """Оптимизация для macOS"""
    if platform.system() == 'Darwin':
        os.environ['PYTHONASYNCIODEBUG'] = '0'
        os.environ['QASYNC_DEBUG'] = '0'
        return True
    return False


def setup_logger(name="TelegramAutoBot"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    log_file = config.get_log_file()

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def random_delay(base, variation=0.2):
    return base * (1 + random.uniform(-variation, variation))


def format_time(seconds):
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def validate_runtime_state(channels=None, pairs=None, comment_text="", require_comment=False):
    """Возвращает список проблем перед запуском задачи."""
    issues = []
    if channels is not None and not channels:
        issues.append("список каналов пуст")
    if pairs is not None and not pairs:
        issues.append("список связок пуст")
    if require_comment and not str(comment_text or "").strip():
        issues.append("текст комментария не заполнен")
    return issues


def format_validation_errors(issues):
    return "; ".join(issues)
