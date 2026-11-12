""" src/logg.py модуль инициализации логгирования"""

import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def setup_logger(name: str, log_file: str, level: int = logging.DEBUG) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    # Защита от дублирования хендлеров при многократном вызове
    if logger.handlers:
        return logger

    log_path = Path(log_file)
    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file, mode='w', encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s: %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
