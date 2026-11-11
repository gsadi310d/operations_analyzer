# src/views.py
"""Формирование JSON-ответов для страниц «Главная» и «События»."""
from __future__ import annotations
from functools import cache

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, List, Tuple

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - dotenv не обязателен для запуска
    pass

from src.utils import filter_transactions_from_month_start, get_greeting, parse_date

logger = logging.getLogger(__name__)

APILAYER_KEY = os.getenv("APILAYER_KEY", "")
FMP_KEY = os.getenv("FMP_KEY", "")
_HAS_APILAYER = bool(APILAYER_KEY) and not APILAYER_KEY.startswith("your_")
_HAS_FMP = bool(FMP_KEY) and not FMP_KEY.startswith("your_")

FALLBACK_CURRENCY_RATES = {"USD": 73.21, "EUR": 87.08}
FALLBACK_STOCK_PRICES = {
    "AAPL": 150.12,
    "AMZN": 3173.18,
    "GOOGL": 2742.39,
    "MSFT": 296.71,
    "TSLA": 1007.08,
}
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
    """Курсы валют к рублю; при недоступности API — запасные значения.

    :param currencies: список кодов валют.
    :return: список словарей {'currency': ..., 'rate': ...}.
    """
    if not _HAS_APILAYER:
        logger.warning("Ключ APILAYER_KEY не задан, используются запасные курсы валют")
        return [{"currency": c, "rate": FALLBACK_CURRENCY_RATES.get(c, 1.0)} for c in currencies]
    try:
        response = requests.get(
            "https://api.apilayer.com/currency_data/live",
            params={"base": "RUB"},
            headers={"apikey": APILAYER_KEY},
            timeout=5,
        )
        response.raise_for_status()
        quotes = response.json().get("quotes", {})
        result = []
        for code in currencies:
            rate = quotes.get(f"RUB{code}")
            result.append({"currency": code, "rate": round(1 / float(rate), 2) if rate else
                           FALLBACK_CURRENCY_RATES.get(code, 1.0)})
        return result
    except (requests.RequestException, ValueError, ZeroDivisionError) as exc:
        logger.warning("Курсы валют недоступны (%s), используются запасные значения", exc)
        return [{"currency": c, "rate": FALLBACK_CURRENCY_RATES.get(c, 1.0)} for c in currencies]


def get_stock_prices(stocks: List[str]) -> List[dict]:
    """Стоимость акций из S&P 500; при недоступности API — запасные значения.

    :param stocks: список тикеров.
    :return: список словарей {'stock': ..., 'price': ...}.
    """
    if not _HAS_FMP:
        logger.warning("Ключ FMP_KEY не задан, используются запасные цены акций")
        return [{"stock": s, "price": FALLBACK_STOCK_PRICES.get(s, 0.0)} for s in stocks]
    try:
        url = "https://financialmodelingprep.com/api/v3/quote-short/" + ",".join(stocks)
        response = requests.get(url, params={"apikey": FMP_KEY}, timeout=5)
        response.raise_for_status()
        quotes = {item["symbol"]: item["price"] for item in response.json()}
        return [{"stock": s, "price": float(quotes.get(s, FALLBACK_STOCK_PRICES.get(s, 0.0)))}
                for s in stocks]
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Цены акций недоступны (%s), используются запасные значения", exc)
        return [{"stock": s, "price": FALLBACK_STOCK_PRICES.get(s, 0.0)} for s in stocks]


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
    top = sorted(period, key=lambda r: abs(float(r.get("Сумма платежа", 0))), reverse=True)[:5]
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
    """Определяет диапазон дат по периоду W/M/Y/ALL; неизвестный период — месяц."""
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

    :param date_str: дата.
    :param transactions: транзакции (список словарей или DataFrame).
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
