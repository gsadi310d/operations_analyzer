#src/utils.py
"""Вспомогательные функции: чтение Excel, парсинг дат и приветствие."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Union

import pandas as pd

logger = logging.getLogger(__name__)


def read_transactions_excel(file_path: str) -> pd.DataFrame:
    """Читает Excel-файл с транзакциями и приводит колонки дат к datetime.

    :param file_path: Путь к Excel-файлу.
    :return: DataFrame с транзакциями.
    """
    logger.info("Чтение файла %s", file_path)
    df = pd.read_excel(file_path)
    for col in ("Дата операции", "Дата платежа"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    logger.info("Загружено строк: %s", len(df))
    return df


def parse_date(date_str: str) -> datetime:
    """Парсит дату в форматах 'YYYY-MM-DD HH:MM:SS', 'YYYY-MM-DD',
    'DD.MM.YYYY HH:MM:SS', 'DD.MM.YYYY'.

    :param date_str: строка с датой.
    :return: объект datetime.
    :raises ValueError: если формат неизвестен.
    """
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Неизвестный формат даты: {date_str!r}")


def get_greeting(current_time: Union[datetime, str]) -> str:
    """Возвращает приветствие по интервалам.

    06:00-11:59 — 'Доброе утро', 12:00-17:59 — 'Добрый день',
    18:00-22:59 — 'Добрый вечер', 23:00-05:59 — 'Доброй ночи'.

    :param current_time: Datetime или строка 'YYYY-MM-DD HH:MM:SS'.
    :return: Строка приветствия.
    """
    if isinstance(current_time, str):
        current_time = parse_date(current_time)
    hour = current_time.hour
    if 6 <= hour < 12:
        return "Доброе утро"
    if 12 <= hour < 18:
        return "Добрый день"
    if 18 <= hour < 23:
        return "Добрый вечер"
    return "Доброй ночи"


def filter_transactions_from_month_start(transactions: Any, date_str: str) -> List[dict]:
    """Возвращает транзакции с начала месяца даты по саму дату включительно.

    :param transactions: Список словарей или DataFrame с транзакциями.
    :param date_str: Дата в любом поддерживаемом формате.
    :return: Список словарей с транзакциями за период.
    """
    end = parse_date(date_str)
    start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = end.replace(hour=23, minute=59, second=59)
    result: List[dict] = []
    if hasattr(transactions, "to_dict"):
        transactions = transactions.to_dict("records")
    for row in transactions:
        dt = row.get("Дата операции")
        if isinstance(dt, str):
            try:
                dt = parse_date(dt)
            except ValueError:
                continue
        if dt is not None and start <= dt <= end:
            result.append(row)
    return result
