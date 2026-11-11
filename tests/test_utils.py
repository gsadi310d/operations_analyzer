#test_utils.py

"""Тесты утилит: приветствие, даты, чтение Excel, фильтрация."""
from datetime import datetime

import pytest

from src.utils import (
    filter_transactions_from_month_start,
    get_greeting,
    parse_date,
    read_transactions_excel,
)


@pytest.mark.parametrize(
    "hour,expected",
    [
        (5, "Доброй ночи"),
        (6, "Доброе утро"),
        (11, "Доброе утро"),
        (12, "Добрый день"),
        (17, "Добрый день"),
        (18, "Добрый вечер"),
        (22, "Добрый вечер"),
        (23, "Доброй ночи"),
    ],
)
def test_greeting_intervals(hour, expected):
    assert get_greeting(f"2021-12-20 {hour:02d}:00:00") == expected


def test_greeting_datetime_object():
    assert get_greeting(datetime(2021, 12, 20, 12, 30)) == "Добрый день"


def test_parse_date_all_formats():
    assert parse_date("2021-12-20 20:00:00") == datetime(2021, 12, 20, 20, 0)
    assert parse_date("2021-12-20") == datetime(2021, 12, 20)
    assert parse_date("20.12.2021") == datetime(2021, 12, 20)


def test_parse_date_invalid():
    with pytest.raises(ValueError):
        parse_date("20/12/2021")


def test_read_transactions_excel():
    df = read_transactions_excel("data/operations.xlsx")
    assert len(df) == 30
    assert "Сумма платежа" in df.columns
    assert "Дата операции" in df.columns


def test_filter_from_month_start(sample_transactions):
    result = filter_transactions_from_month_start(sample_transactions, "26.12.2021")
    assert len(result) == 17


def test_filter_from_month_start_includes_edge_day(sample_transactions):
    result = filter_transactions_from_month_start(sample_transactions, "01.12.2021")
    assert len(result) == 1
    assert result[0]["Описание"] == "Перекрёсток"


def test_filter_empty_for_other_month(sample_transactions):
    assert filter_transactions_from_month_start(sample_transactions, "05.05.2022") == []
