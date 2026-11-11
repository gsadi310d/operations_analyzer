# test_services.py

"""Тесты сервисов: кешбэк, Инвесткопилка, поиски, переводы."""
import json

import pandas as pd

from src.services import (cashback_categories, investment_bank,
                          search_phone_numbers, simple_search,
                          transfers_to_individuals)


def test_cashback_categories_december(sample_transactions):
    data = json.loads(cashback_categories(sample_transactions, 2021, 12))
    assert data["ЖКХ"] == 142.16
    assert data["Супермаркеты"] == 29.77
    assert data["Мобильная связь"] == 2.9
    assert len(data) == 9


def test_cashback_categories_november(sample_transactions):
    data = json.loads(cashback_categories(sample_transactions, 2021, 11))
    assert data["Топливо"] == 22.89
    assert data["Медицина"] == 13.5
    assert "ЖКХ" not in data


def test_cashback_empty_month(sample_transactions):
    assert json.loads(cashback_categories(sample_transactions, 2020, 1)) == {}


def test_investment_bank_example():
    transactions = [
        {"Дата операции": pd.Timestamp("2021-12-01"), "Сумма платежа": -1712.0}
    ]
    assert investment_bank("2021-12", transactions, 50) == 38.0


def test_investment_bank_december(sample_transactions):
    assert investment_bank("2021-12", sample_transactions, 50) == 146.55
    assert investment_bank("2021-12", sample_transactions, 10) == 6.55


def test_investment_bank_other_month(sample_transactions):
    assert investment_bank("2020-01", sample_transactions, 50) == 0.0


def test_simple_search_case_insensitive(sample_transactions):
    found = json.loads(simple_search(sample_transactions, "супер"))
    assert len(found) == 7


def test_simple_search_no_results(sample_transactions):
    assert json.loads(simple_search(sample_transactions, "qqqq")) == []


def test_search_phone_numbers(sample_transactions):
    found = json.loads(search_phone_numbers(sample_transactions))
    descriptions = {row["Описание"] for row in found}
    assert len(found) == 4
    assert "МТС +7 921 11-22-33" in descriptions
    assert "Тинькофф Мобайл +7 995 555-55-55" in descriptions
    assert "MTC Mobile +7 981 333-44-55" in descriptions
    assert "Пополнение 89000000000" in descriptions


def test_transfers_to_individuals(sample_transactions):
    found = json.loads(transfers_to_individuals(sample_transactions))
    assert len(found) == 4
    assert {r["Описание"] for r in found} == {"Валерий А.", "Сергей М.", "Мария К.", "Артём П."}
