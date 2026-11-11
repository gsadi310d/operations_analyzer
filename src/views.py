# src/views.py
"""Формирование JSON-ответов для страниц «Главная» и «События»."""
import json
import os
from datetime import datetime, timedelta
from typing import Any, List, Tuple

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv не обязателен для запуска
    def load_dotenv() -> None:
        """Заглушка: без пакета python-dotenv переменные читаются из окружения."""
load_dotenv()

from src.cache import file_cache_get, file_cache_save
from src.logg import setup_logger
from src.utils import filter_transactions_from_month_start, get_greeting, parse_date

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

    :param currencies: Список кодов валют.
    :return: Список словарей {'currency': ..., 'rate': ...}.
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
        if result:
            file_cache_save(key, result)
        return result
    except (requests.RequestException, ValueError, TypeError, ZeroDivisionError) as exc:
        logger.error("Курсы валют недоступны, кэш отсутствует (%s)", exc)
        return []


def get_stock_prices(stocks: List[str]) -> List[dict]:
    """Стоимость акций из S&P 500 с файловым кэшем.

    Порядок: кэш есть — отдаём его; кэша нет — запросы к Alpha Vantage
    (успех = перезапись кэша); API упал и кэша нет — пустой список.
    Тикеры без цены в ответе пропускаются с предупреждением в лог.

    Лимит бесплатного ключа Alpha Vantage: 25 запросов в сутки, ~5 в минуту —
    поэтому каждый тикер равен одному запросу, а ответ кэшируется целиком.

    :param stocks: Список тикеров.
    :return: Список словарей {'stock': ..., 'price': ...}.
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


def main_page(date_str: str, transactions: Any) -> str:
    """JSON-ответ страницы «Главная»: приветствие, карты, топ-5, курсы и акции.

    :param date_str: дата и время 'YYYY-MM-DD HH:MM:SS'.
    :param transactions: транзакции (список словарей или DataFrame).
    :return: JSON-строка с ответом.
    """
    dt = parse_date(date_str)
    period = filter_transactions_from_month_start(transactions, date_str)
    cards: dict = {}
    for row in period:
        amount = row.get("Сумма платежа")
        number = str(row.get("Номер карты", "") or "")
        if len(number) >= 4 and isinstance(amount, (int, float)) and amount < 0:
            digits = number[-4:]
            cards[digits] = cards.get(digits, 0.0) + abs(float(amount))
    top = sorted(
        (r for r in period if isinstance(r.get("Сумма платежа"), (int, float))),
        key=lambda r: abs(float(r["Сумма платежа"])),
        reverse=True,)[:5]
    settings = load_user_settings()
    response = {
        "greeting": get_greeting(dt),
        "cards": [
            {"last_digits": digits, "total_spent": round(total, 2), "cashback": round(total / 100, 2)}
            for digits, total in sorted(cards.items())
        ],
        "top_transactions": [
            {
                "date": row["Дата операции"].strftime("%d.%m.%Y"),
                "amount": round(float(row.get("Сумма платежа", 0)), 2),
                "category": row.get("Категория", ""),
                "description": row.get("Описание", ""),
            }
            for row in top
        ],
        "currency_rates": get_currency_rates(settings.get("user_currencies", ["USD", "EUR"])),
        "stock_prices": get_stock_prices(settings.get("user_stocks", [])),
    }
    return json.dumps(response, ensure_ascii=False, indent=2)


def get_period_range(dt: datetime, period: str) -> Tuple[datetime, datetime]:
    """Определяет диапазон дат по периоду W/M/Y/ALL; неизвестный период — месяц.

    :param dt: Дата, относительно которой считается период.
    :param period: W (неделя), M (месяц), Y (год), ALL (всё время).
    :return: Кортеж (начало, конец) диапазона.
    """
    end = dt.replace(hour=23, minute=59, second=59)
    if period == "W":
        start = dt - timedelta(days=dt.weekday())
    elif period == "Y":
        start = dt.replace(month=1, day=1)
    elif period == "ALL":
        return datetime(1, 1, 1), end
    elif period == "M":
        start = dt.replace(day=1)
    else:
        logger.warning("Неизвестный период %r, используется месяц", period)
        start = dt.replace(day=1)
    return start.replace(hour=0, minute=0, second=0), end


def events_page(date_str: str, transactions: Any, period: str = "M") -> str:
    """JSON-ответ страницы «События»: расходы по категориям, поступления, курсы и акции.

    :param date_str: Дата.
    :param transactions: Транзакции (список словарей или DataFrame).
    :param period: W, M, Y или ALL (по умолчанию M).
    :return: JSON-строка с ответом.
    """
    dt = parse_date(date_str)
    start, end = get_period_range(dt, period)
    if hasattr(transactions, "to_dict"):
        transactions = transactions.to_dict("records")
    rows = []
    for row in transactions:
        dt_op = row.get("Дата операции")
        if dt_op is not None and start <= dt_op <= end:
            rows.append(row)

    expenses: dict = {}
    income: dict = {}
    for row in rows:
        amount = row.get("Сумма платежа")
        if not isinstance(amount, (int, float)):
            continue
        category = row.get("Категория", "Без категории")
        if amount < 0:
            expenses[category] = expenses.get(category, 0.0) + abs(float(amount))
        else:
            income[category] = income.get(category, 0.0) + float(amount)

    sorted_expenses = sorted(expenses.items(), key=lambda x: x[1], reverse=True)
    main_expenses = [
        {"category": cat, "amount": int(round(total))} for cat, total in sorted_expenses[:7]
    ]
    rest = sum(total for _, total in sorted_expenses[7:])
    if rest:
        main_expenses.append({"category": "Остальное", "amount": int(round(rest))})
    transfers_and_cash = [
        {"category": cat, "amount": int(round(total))}
        for cat, total in sorted_expenses
        if cat in ("Наличные", "Переводы")
    ]
    main_income = [
        {"category": cat, "amount": int(round(total))}
        for cat, total in sorted(income.items(), key=lambda x: x[1], reverse=True)
    ]
    settings = load_user_settings()
    response = {
        "expenses": {
            "total_amount": int(round(sum(expenses.values()))),
            "main": main_expenses,
            "transfers_and_cash": transfers_and_cash,
        },
        "income": {"total_amount": int(round(sum(income.values()))), "main": main_income},
        "currency_rates": get_currency_rates(settings.get("user_currencies", ["USD", "EUR"])),
        "stock_prices": get_stock_prices(settings.get("user_stocks", [])),
    }
    return json.dumps(response, ensure_ascii=False, indent=2)