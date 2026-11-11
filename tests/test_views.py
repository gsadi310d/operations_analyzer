# test_views.py

"""Тесты страниц «Главная» и «События»."""
import json

from src.views import events_page, get_period_range, main_page


def test_main_page_structure(sample_transactions):
    data = json.loads(main_page("2021-12-20 20:00:00", sample_transactions))
    assert data["greeting"] == "Добрый вечер"
    assert data["cards"] == [
        {"last_digits": "5814", "total_spent": 16775.42, "cashback": 167.75},
        {"last_digits": "7512", "total_spent": 2698.23, "cashback": 26.98},
    ]
    top = data["top_transactions"]
    assert len(top) == 5
    assert top[0]["amount"] == 33000.0
    assert top[0]["category"] == "Пополнение_BANK007"
    assert top[1]["amount"] == -14216.42
    assert all(len(t["date"].split(".")) == 3 for t in top)


def test_main_page_rates_and_stocks(sample_transactions):
    data = json.loads(main_page("2021-12-20 20:00:00", sample_transactions))
    rates = {r["currency"]: r["rate"] for r in data["currency_rates"]}
    assert set(rates) == {"USD", "EUR"}
    assert all(v > 0 for v in rates.values())
    stocks = {s["stock"]: s["price"] for s in data["stock_prices"]}
    assert set(stocks) == {"AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"}
    assert all(v > 0 for v in stocks.values())


def test_events_month(sample_transactions):
    data = json.loads(events_page("2021-12-28", sample_transactions, "M"))
    expenses = data["expenses"]
    assert expenses["total_amount"] == 22353
    main_cats = expenses["main"]
    assert len(main_cats) == 8
    assert main_cats[0] == {"category": "ЖКХ", "amount": 14216}
    assert main_cats[-1] == {"category": "Остальное", "amount": 490}
    assert expenses["transfers_and_cash"] == [
        {"category": "Переводы", "amount": 1570},
        {"category": "Наличные", "amount": 800},
    ]
    assert data["income"]["total_amount"] == 58000
    assert data["income"]["main"][0]["category"] == "Пополнение_BANK007"


def test_events_periods(sample_transactions):
    week = json.loads(events_page("2021-12-28", sample_transactions, "W"))
    year = json.loads(events_page("2021-12-28", sample_transactions, "Y"))
    all_period = json.loads(events_page("2021-12-28", sample_transactions, "ALL"))
    bad = json.loads(events_page("2021-12-28", sample_transactions, "Q"))
    month = json.loads(events_page("2021-12-28", sample_transactions, "M"))
    assert week["expenses"]["total_amount"] == 500
    assert year["expenses"]["total_amount"] == 35016
    assert all_period["expenses"]["total_amount"] == 35016
    assert bad["expenses"]["total_amount"] == month["expenses"]["total_amount"]


def test_get_period_range_unknown_defaults_to_month():
    from datetime import datetime

    start, end = get_period_range(datetime(2021, 12, 28), "Q")
    assert (start.day, start.month) == (1, 12)
    assert end.day == 28
