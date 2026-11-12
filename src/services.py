""" src/services.py Сервисы: кешбэк по категориям, Инвесткопилка, поиски, переводы физлицам."""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List

from src.logg import setup_logger

logger = setup_logger("servises", "logs/servises.log")

PHONE_PATTERN = re.compile(r"(?:\+7|8)[\s\-(]*(?:\d[\s\-)]*){9,11}")
INDIVIDUAL_NAME_PATTERN = re.compile(r"\b[А-ЯЁ][а-яё]+\s[А-ЯЁ]\.")


def cashback_categories(transactions: List[dict[str, Any]], year: int, month: int) -> str:
    """Анализ выгодных категорий повышенного кешбэка за указанный месяц.

    :param transactions: список словарей с транзакциями.
    :param year: год анализа.
    :param month: месяц анализа.
    :return: JSON-строка вида {'Категория': сумма кешбэка}.
    """
    totals: Dict[str, float] = {}
    for row in transactions:
        dt = row.get("Дата операции")
        if dt is None or dt.year != year or dt.month != month:
            continue
        amount = row.get("Сумма платежа")
        if isinstance(amount, (int, float)) and amount < 0:
            category = row.get("Категория", "Без категории")
            totals[category] = totals.get(category, 0.0) + abs(float(amount))
    cashback = {cat: round(total / 100, 2) for cat, total in sorted(totals.items())}
    logger.info("Отчет сформирован")
    return json.dumps(cashback, ensure_ascii=False, indent=2)


def investment_bank(month: str, transactions: List[dict[str, Any]], limit: int) -> float:
    """Рассчитывает сумму для «Инвесткопилки» через округление трат.

    :param month: месяц в формате 'YYYY-MM'.
    :param transactions: список словарей с транзакциями.
    :param limit: порог округления (10, 50 или 100).
    :return: сумма, которая ушла бы в Инвесткопилку.
    """
    logger.info(month)
    saved = 0.0
    for row in transactions:
        dt = row.get("Дата операции")
        if dt is None or f"{dt.year:04d}-{dt.month:02d}" != month:
            continue
        amount = row.get("Сумма платежа")
        if not isinstance(amount, (int, float)) or amount >= 0:
            continue
        spent = abs(float(amount))
        saved += math.ceil(spent / limit) * limit - spent
    logger.info("Инвесткопилка за %s при пороге %s: %s", month, limit, saved)
    return round(saved, 2)


def simple_search(transactions: List[dict[str, Any]], search: str) -> str:
    """Ищет транзакции по подстроке в описании или категории без учёта регистра.

    :param transactions: список словарей с транзакциями.
    :param search: строка поиска.
    :return: JSON-строка со списком найденных транзакций.
    """
    needle = str(search).strip().lower()
    found = []
    for row in transactions:
        haystack = (
            str(row.get("Описание", "")).lower() + " " + str(row.get("Категория", "")).lower()
        )
        if needle in haystack:
            found.append(row)
    logger.info("Отчет сформирован")
    return json.dumps(found, ensure_ascii=False, indent=2, default=str)


def search_phone_numbers(transactions: List[dict[str, Any]]) -> str:
    """Ищет транзакции, в описании которых есть мобильные номера.

    Поддерживаются форматы '+7 (900) 000-00-00', '89000000000', '+7 921 11-22-33'.

    :param transactions: список словарей с транзакциями.
    :return: JSON-строка со списком найденных транзакций.
    """
    found = [row for row in transactions if PHONE_PATTERN.search(str(row.get("Описание", "")))]
    logger.info("Отчет сформирован")
    return json.dumps(found, ensure_ascii=False, indent=2, default=str)


def transfers_to_individuals(transactions: List[dict[str, Any]]) -> str:
    """Ищет переводы физлицам: категория 'Переводы' и имя с инициалом в описании.

    :param transactions: список словарей с транзакциями.
    :return: JSON-строка со списком найденных транзакций.
    """
    found = []
    for row in transactions:
        if row.get("Категория") != "Переводы":
            continue
        description = str(row.get("Описание", ""))
        if INDIVIDUAL_NAME_PATTERN.search(description):
            found.append(row)
    logger.info("Отчет сформирован")
    return json.dumps(found, ensure_ascii=False, indent=2, default=str)
