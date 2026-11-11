#src/reports.py
"""Отчёты: траты по категории, по дням недели, в рабочий/выходной день."""
from __future__ import annotations

import functools
import json
import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import pandas as pd

from src.utils import parse_date

logger = logging.getLogger(__name__)

WEEKDAY_NAMES = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}


def save_to_file(filename: Optional[str] = None) -> Callable:
    """Декоратор: сохраняет результат отчёта в JSON в папку reports/.

    Без параметра имя файла — '<имя_функции>_report.json',
    с параметром — указанное имя файла.

    :param filename: необязательное имя файла отчёта.
    :return: декоратор.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            target = filename or f"{func.__name__}_report.json"
            os.makedirs("reports", exist_ok=True)
            path = os.path.join("reports", target)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            logger.info("Отчёт сохранён в %s", path)
            return result

        return wrapper

    return decorator


def last_three_months_mask(df: pd.DataFrame, end: datetime) -> pd.Series:
    """Даты операций за последние три месяца до end включительно."""
    start = end - pd.DateOffset(months=3)
    return (df["Дата операции"] >= start) & (df["Дата операции"] <= end)


@save_to_file()
def spending_by_category(df: pd.DataFrame, category: str, date: Optional[str] = None) -> dict:
    """Траты по категории за последние три месяца от даты (или от текущей).

    :param df: DataFrame с транзакциями.
    :param category: название категории.
    :param date: опорная дата (необязательно).
    :return: словарь {'category': ..., 'total': ...}.
    """
    end = parse_date(date) if date else datetime.now()
    mask = last_three_months_mask(df, end) & (df["Категория"] == category)
    spends = df.loc[mask & (df["Сумма платежа"] < 0), "Сумма платежа"].abs()
    total = round(float(spends.sum()), 2)
    logger.info("Траты по категории %s за 3 месяца от %s: %s", category, end.date(), total)
    return {"category": category, "total": total}


@save_to_file()
def spending_by_weekday(df: pd.DataFrame, date: Optional[str] = None) -> dict:
    """Средние траты в каждый день недели за последние три месяца.

    :param df: DataFrame с транзакциями.
    :param date: опорная дата (необязательно).
    :return: словарь {'День недели': средняя трата}.
    """
    end = parse_date(date) if date else datetime.now()
    mask = last_three_months_mask(df, end) & (df["Сумма платежа"] < 0)
    sub = df.loc[mask]
    spends = sub["Сумма платежа"].abs()
    weekdays = sub["Дата операции"].dt.dayofweek
    result: Dict[str, float] = {}
    for wd in range(7):
        values = spends[weekdays == wd]
        if len(values):
            result[WEEKDAY_NAMES[wd]] = round(float(values.mean()), 2)
    return result


@save_to_file()
def spending_by_workday_weekend(df: pd.DataFrame, date: Optional[str] = None) -> dict:
    """Средние траты в рабочий и в выходной день за последние три месяца.

    :param df: DataFrame с транзакциями.
    :param date: опорная дата (необязательно).
    :return: словарь {'рабочий': ..., 'выходной': ...}.
    """
    end = parse_date(date) if date else datetime.now()
    mask = last_three_months_mask(df, end) & (df["Сумма платежа"] < 0)
    sub = df.loc[mask]
    spends = sub["Сумма платежа"].abs()
    weekdays = sub["Дата операции"].dt.dayofweek
    workday = spends[weekdays < 5]
    weekend = spends[weekdays >= 5]
    return {
        "рабочий": round(float(workday.mean()), 2) if len(workday) else 0.0,
        "выходной": round(float(weekend.mean()), 2) if len(weekend) else 0.0,
    }
