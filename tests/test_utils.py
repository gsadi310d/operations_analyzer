"""Тесты утилит: чтение Excel, парсинг дат, приветствие, фильтрация."""
from datetime import datetime

import pandas as pd
import pytest

from src.utils import (
    filter_transactions_from_month_start,
    get_greeting,
    parse_date,
    read_transactions_excel,
)


@pytest.fixture
def sample_transactions():
    """Контрольный набор транзакций за декабрь 2021 и май 2022 года."""
    return [
        {"Дата операции": datetime(2021, 12, 1, 10, 0, 0),
         "Сумма платежа": -150.0, "Категория": "Супермаркеты", "Описание": "Перекрёсток"},
        {"Дата операции": datetime(2021, 12, 1, 18, 30, 0),
         "Сумма платежа": -200.0, "Категория": "ЖКХ", "Описание": "Электричество"},
        {"Дата операции": datetime(2021, 12, 5, 12, 0, 0),
         "Сумма платежа": -1000.0, "Категория": "Супермаркеты", "Описание": "Пятёрочка"},
        {"Дата операции": datetime(2021, 12, 10, 9, 0, 0),
         "Сумма платежа": 50000.0, "Категория": "Зарплата", "Описание": "Оклад"},
        {"Дата операции": datetime(2021, 12, 26, 20, 0, 0),
         "Сумма платежа": -300.0, "Категория": "Рестораны", "Описание": "Кафе"},
        {"Дата операции": datetime(2021, 12, 27, 11, 0, 0),
         "Сумма платежа": -100.0, "Категория": "Топливо", "Описание": "АЗС"},
        {"Дата операции": datetime(2022, 5, 10, 14, 0, 0),
         "Сумма платежа": -750.0, "Категория": "Рестораны", "Описание": "Кафе"},
    ]


# ---------- get_greeting ----------


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
        (0, "Доброй ночи"),
    ],
)
def test_greeting_intervals(hour, expected):
    assert get_greeting(f"2021-12-20 {hour:02d}:00:00") == expected


def test_greeting_datetime_object():
    assert get_greeting(datetime(2021, 12, 20, 12, 30)) == "Добрый день"


# ---------- parse_date ----------


def test_parse_date_all_formats():
    assert parse_date("2021-12-20 20:00:00") == datetime(2021, 12, 20, 20, 0)
    assert parse_date("2021-12-20") == datetime(2021, 12, 20)
    assert parse_date("20.12.2021") == datetime(2021, 12, 20)


def test_parse_date_strips_whitespace():
    assert parse_date("  20.12.2021  ") == datetime(2021, 12, 20)


def test_parse_date_invalid():
    with pytest.raises(ValueError):
        parse_date("20/12/2021")


# ---------- read_transactions_excel ----------


def test_read_transactions_excel(tmp_path):
    df_in = pd.DataFrame({
        "Дата операции": ["01.12.2021 10:00:00", "05.12.2021 12:30:00"],
        "Дата платежа": ["01.12.2021", "05.12.2021"],
        "Сумма платежа": [-1000.0, -2500.0],
        "Категория": ["Супермаркеты", "Переводы"],
        "Описание": ["Перекрёсток", "Перевод"],
    })
    path = tmp_path / "operations.xlsx"
    df_in.to_excel(path, index=False)

    df = read_transactions_excel(str(path))
    assert len(df) == 2
    assert "Сумма платежа" in df.columns
    assert "Дата операции" in df.columns
    # даты приведены к datetime
    assert isinstance(df["Дата операции"].iloc[0], pd.Timestamp)
    assert df["Дата платежа"].iloc[0] == pd.Timestamp("2021-12-01")


def test_read_transactions_excel_without_payment_column(tmp_path):
    """Колонка «Дата платежа» необязательна: без неё функция не падает."""
    df_in = pd.DataFrame({
        "Дата операции": ["01.12.2021"],
        "Сумма платежа": [-100.0],
    })
    path = tmp_path / "operations.xlsx"
    df_in.to_excel(path, index=False)

    df = read_transactions_excel(str(path))
    assert len(df) == 1
    assert "Дата платежа" not in df.columns


# ---------- filter_transactions_from_month_start ----------


def test_filter_from_month_start(sample_transactions):
    result = filter_transactions_from_month_start(sample_transactions, "26.12.2021")
    # 1, 5, 10 и 26 декабря включительно; 27-е — уже за пределами
    assert len(result) == 5
    descriptions = {row["Описание"] for row in result}
    assert "АЗС" not in descriptions


def test_filter_from_month_start_includes_edge_day(sample_transactions):
    result = filter_transactions_from_month_start(sample_transactions, "01.12.2021")
    assert len(result) == 2
    assert "Перекрёсток" in [row["Описание"] for row in result]


def test_filter_includes_end_of_day(sample_transactions):
    """Транзакция в 23:59:59 последнего дня попадает в диапазон."""
    row = {"Дата операции": datetime(2021, 12, 31, 23, 59, 59), "Сумма платежа": -50.0}
    result = filter_transactions_from_month_start(sample_transactions + [row], "31.12.2021")
    assert row in result


def test_filter_empty_for_other_month(sample_transactions):
    assert filter_transactions_from_month_start(sample_transactions, "05.05.2022") == []


def test_filter_accepts_dataframe(sample_transactions):
    df = pd.DataFrame(sample_transactions)
    result = filter_transactions_from_month_start(df, "05.12.2021")
    assert len(result) == 3
    assert all(isinstance(row, dict) for row in result)


def test_filter_accepts_string_dates(sample_transactions):
    """Даты в виде строк тоже парсятся и попадают в диапазон."""
    rows = [{"Дата операции": "03.12.2021 08:00:00", "Сумма платежа": -10.0}]
    result = filter_transactions_from_month_start(rows, "05.12.2021")
    assert len(result) == 1


def test_filter_skips_unparseable_dates(sample_transactions):
    """Строку с неизвестным форматом даты функция молча пропускает."""
    rows = sample_transactions + [{"Дата операции": "не дата", "Сумма платежа": -1.0}]
    result = filter_transactions_from_month_start(rows, "26.12.2021")
    assert len(result) == 5
