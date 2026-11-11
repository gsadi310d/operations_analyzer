# src/cache.py
import json
import os
import time
from typing import Any, Optional
import logging as logger
from cachetools import TTLCache

API_CACHE_FILE = "data/api_cache.json"
API_CACHE_TTL_MEMORY = 300     # 5 минут: страницы дергают API несколько раз за запуск
API_CACHE_TTL_FILE = 86_400    # сутки: курсы ЦБ обновляются раз в день

# timer=time.monotonic — не боится перевода системных часов
_rates_cache: TTLCache = TTLCache(maxsize=8, ttl=API_CACHE_TTL_MEMORY, timer=time.monotonic)
_stocks_cache: TTLCache = TTLCache(maxsize=8, ttl=API_CACHE_TTL_MEMORY, timer=time.monotonic)


# ---------- Второй слой: файловый кэш ----------

def file_cache_load() -> dict:
    """Читает кэш-файл; если файла нет или он повреждён — возвращает пустой словарь."""
    try:
        with open(API_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def file_cache_save(key: str, data: Any) -> None:
    """Сохраняет блок данных в кэш-файл, создавая директорию при необходимости."""
    cache = file_cache_load()
    cache[key] = {"timestamp": time.time(), "data": data}
    try:
        os.makedirs(os.path.dirname(API_CACHE_FILE) or ".", exist_ok=True)
        with open(API_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.warning("Не удалось сохранить кэш API (%s)", exc)


def file_cache_get(key: str, ttl: int = API_CACHE_TTL_FILE) -> Optional[Any]:
    """Возвращает данные из файла, если они свежее ttl, иначе None."""
    entry = file_cache_load().get(key)
    if not isinstance(entry, dict) or "timestamp" not in entry:
        return None
    if time.time() - entry["timestamp"] > ttl:
        return None
    return entry.get("data")


# ---------- Общая логика двух уровней ----------

def cached_get(key: str, memory_cache: TTLCache, fetcher) -> Any:
    """Достаёт данные: память → файл → API. Успех API пишется в оба слоя."""
    # L1: память
    if key in memory_cache:
        logger.info("Кэш L1: значение для %s взято из памяти", key)
        return memory_cache[key]

    # L2: файл
    from_file = file_cache_get(key)
    if from_file is not None:
        logger.info("Кэш L2: значение для %s взято из файла", key)
        memory_cache[key] = from_file  # прогрели L1, чтобы дальше не читать диск
        return from_file

    # Сеть
    fresh = fetcher()
    if fresh is None:
        # запасные значения не кэшируем: после появления ключа или сети
        # следующая попытка снова пойдёт в API
        return None
    memory_cache[key] = fresh
    file_cache_save(key, fresh)
    return fresh
