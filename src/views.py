# src/views.py
"""Формирование JSON-ответов для страниц «Главная» и «События»."""
import json
import os
from typing import List

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - dotenv не обязателен для запуска
    pass

from src.cache import file_cache_get, file_cache_save
from src.logg import setup_logger

logger = setup_logger("views", "logs/views.log")

API_CURRENCY_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
API_STOCK_URL = "https://www.alphavantage.co/query"
API_STOCK_KEY = os.getenv("API_STOCK_KEY", "")
_HAS_API_STOCK = bool(API_STOCK_KEY) and not API_STOCK_KEY.startswith("your_")

DEFAULT_SETTINGS = {
    "user_currencies": ["USD", "EUR"],
    "user_stocks": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"],
}


def load_user_settings(path: str = "user_settings.json") -> dict:
    """Читает пользовательские настройки; при ошибке — настройки по умолчанию."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.warning("Не удалось прочитать %s, используются настройки по умолчанию", path)
        return dict(DEFAULT_SETTINGS)


def get_currency_rates(currencies: List[str]) -> List[dict]:
    """Курсы валют к рублю по данным ЦБ РФ с файловым кэшем.

    Порядок: кэш есть — отдаём его; кэша нет — запрос к API
    (успех = перезапись кэша); API упал и кэша нет — пустой список.
    Валюты, отсутствующие в ответе ЦБ, пропускаются с предупреждением в лог.

    :param currencies: список кодов валют.
    :return: список словарей {'currency': ..., 'rate': ...}.
    """
    key = "currency_rates:" + ",".join(sorted(set(currencies)))

    cached = file_cache_get(key)
    if cached is not None:
        return cached

    try:
        response = requests.get(API_CURRENCY_URL, timeout=5)
        response.raise_for_status()
        valute = response.json().get("Valute", {})

        result = []
        for code in currencies:
            entry = valute.get(code)
            if entry and entry.get("Value"):
                nominal = float(entry.get("Nominal", 1))
                rate = round(float(entry["Value"]) / nominal, 2)
                result.append({"currency": code, "rate": rate})
            else:
                logger.warning("Курс для %s не найден в ответе ЦБ", code)
        file_cache_save(key, result)
        if result:
            file_cache_save(key, result)
        return result
    except (requests.RequestException, ValueError, TypeError, ZeroDivisionError) as exc:
        logger.error("Курсы валют недоступны, кэш отсутствует")
        return []


def get_stock_prices(stocks: List[str]) -> List[dict]:
    """Стоимость акций из S&P 500 с файловым кэшем.

    Порядок: кэш есть — отдаём его; кэша нет — запросы к Alpha Vantage
    (успех = перезапись кэша); API упал и кэша нет — пустой список.
    Тикеры без цены в ответе пропускаются с предупреждением в лог.

    Лимит бесплатного ключа Alpha Vantage: 25 запросов в сутки, ~5 в минуту —
    поэтому каждый тикер равен одному запросу, а ответ кэшируется целиком.

    :param stocks: список тикеров.
    :return: список словарей {'stock': ..., 'price': ...}.
    """
    key = "stock_prices:" + ",".join(sorted(set(stocks)))

    cached = file_cache_get(key)
    if cached is not None:
        return cached

    if not _HAS_API_STOCK:
        logger.error("Ключ API_STOCK_KEY не задан, кэш отсутствует")
        return []

    result = []
    try:
        for symbol in stocks:
            response = requests.get(
                API_STOCK_URL,
                params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": API_STOCK_KEY},
                timeout=5,
            )
            response.raise_for_status()
            quote = response.json().get("Global Quote", {})
            price = quote.get("05. price")
            if price:
                result.append({"stock": symbol, "price": round(float(price), 2)})
            else:
                logger.warning("Цена для %s не получена", symbol)
        if result:
            file_cache_save(key, result)
        return result
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.error("Цены акций недоступны, кэш отсутствует (%s)", exc)
        return []
