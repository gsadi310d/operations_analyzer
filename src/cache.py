# src/cache.py
"""Файловый кэш для ответов внешних API."""
import json
import os
import time
from typing import Any, Optional

from src.logg import setup_logger

logger = setup_logger("cache", "logs/cache.log")
API_CACHE_FILE = "data/api_cache.json"


def file_cache_load(path: str = API_CACHE_FILE) -> dict[str, Any]:
    """Читает кэш-файл; при отсутствии или повреждении — пустой словарь."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def file_cache_save(key: str, data: Any, path: str = API_CACHE_FILE) -> None:
    """Перезаписывает блок данных в кэше, создавая директорию при необходимости."""
    cache = file_cache_load(path)
    cache[key] = {"timestamp": time.time(), "data": data}
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.warning("Не удалось сохранить кэш API (%s)", exc)


def file_cache_get(key: str, path: str = API_CACHE_FILE) -> Optional[Any]:
    """Возвращает данные из кэша любой давности или None, если ключа нет.

    Свежесть не проверяется: любое сохранённое значение лучше, чем ничего —
    это запасной источник при недоступном API.
    """
    entry = file_cache_load(path).get(key)
    if isinstance(entry, dict):
        return entry.get("data")
    return None
