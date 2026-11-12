"""Тесты страниц «Главная» и «События», API-функций и загрузки настроек."""
import json
from datetime import datetime
from unittest.mock import patch

import pytest

import src.views as views
from src.views import (events_page, get_currency_rates, get_period_range, get_stock_prices, load_user_settings,
                       main_page)

# ---------- Вспомогательные моки ----------


class FakeResponse:
    """Заглушка ответа requests: raise_for_status не бросает, json возвращает заданное."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture
def no_cache(monkeypatch):
    """Отключает файловый кэш: чтение всегда None, запись запоминается в словарь."""
    saved = {}
    monkeypatch.setattr(views, "file_cache_get", lambda key: None)
    monkeypatch.setattr(views, "file_cache_save", lambda key, data: saved.setdefault(key, data))
    return saved


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    """Временный user_settings.json; путь передаётся в load_user_settings через cwd."""
    path = tmp_path / "user_settings.json"
    path.write_text(
        json.dumps({"user_currencies": ["USD"], "user_stocks": ["AAPL"]}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return path


@pytest.fixture
def transactions():
    """Контрольный набор транзакций за декабрь 2021 и ноябрь 2021 года."""
    return [
        {"Дата операции": datetime(2021, 12, 1, 10, 0, 0),
         "Сумма платежа": -1000.0, "Номер карты": "*4589",
         "Категория": "Супермаркеты", "Описание": "Пятёрочка"},
        {"Дата операции": datetime(2021, 12, 5, 12, 30, 0),
         "Сумма платежа": -2500.0, "Номер карты": "*4589",
         "Категория": "Переводы", "Описание": "Перевод И.И.Иванову"},
        {"Дата операции": datetime(2021, 12, 10, 18, 0, 0),
         "Сумма платежа": 50000.0, "Номер карты": "*7123",
         "Категория": "Зарплата", "Описание": "Оклад"},
        {"Дата операции": datetime(2021, 12, 15, 9, 0, 0),
         "Сумма платежа": -300.0, "Номер карты": "*7123",
         "Категория": "Наличные", "Описание": "Снятие"},
        {"Дата операции": datetime(2021, 11, 20, 14, 0, 0),
         "Сумма платежа": -750.0, "Номер карты": "*4589",
         "Категория": "Рестораны", "Описание": "Кафе"},
    ]


# ---------- load_user_settings ----------


def test_load_user_settings_reads_file(settings_file):
    result = load_user_settings()
    assert result == {"user_currencies": ["USD"], "user_stocks": ["AAPL"]}


def test_load_user_settings_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # файла нет
    result = load_user_settings()
    assert result == dict(views.DEFAULT_SETTINGS)


def test_load_user_settings_invalid_json(tmp_path, monkeypatch):
    (tmp_path / "user_settings.json").write_text("{не json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = load_user_settings()
    assert result == dict(views.DEFAULT_SETTINGS)


# ---------- get_currency_rates ----------


def test_currency_rates_success(no_cache, monkeypatch):
    payload = {"Valute": {"USD": {"Value": 75.5, "Nominal": 1},
                          "EUR": {"Value": 100.0, "Nominal": 2}}}
    monkeypatch.setattr(views.requests, "get", lambda *a, **kw: FakeResponse(payload))

    result = get_currency_rates(["USD", "EUR"])

    assert result == [{"currency": "USD", "rate": 75.5}, {"currency": "EUR", "rate": 50.0}]
    # успешный непустой результат сохранён в кэш
    assert any(key.startswith("currency_rates:") for key in no_cache)


def test_currency_rates_uses_cache(monkeypatch):
    cached = [{"currency": "USD", "rate": 70.0}]
    monkeypatch.setattr(views, "file_cache_get", lambda key: cached)

    def fail(*args, **kwargs):
        raise AssertionError("Сеть не должна вызываться при наличии кэша")

    monkeypatch.setattr(views.requests, "get", fail)
    assert get_currency_rates(["USD"]) == cached


def test_currency_rates_missing_code_is_skipped(no_cache, monkeypatch):
    payload = {"Valute": {"USD": {"Value": 75.5, "Nominal": 1}}}
    monkeypatch.setattr(views.requests, "get", lambda *a, **kw: FakeResponse(payload))

    result = get_currency_rates(["USD", "XYZ"])
    assert result == [{"currency": "USD", "rate": 75.5}]
    # пустой результат не кэшируется — здесь непустой, но проверим негатив ниже


def test_currency_rates_api_failure(no_cache, monkeypatch):
    class Broken:
        def raise_for_status(self):
            raise views.requests.RequestException("network down")

    monkeypatch.setattr(views.requests, "get", lambda *a, **kw: Broken())
    assert get_currency_rates(["USD"]) == []


def test_currency_rates_empty_result_not_cached(no_cache, monkeypatch):
    """Если ЦБ не вернул ни одной валюты, пустой список не должен попасть в кэш."""
    monkeypatch.setattr(views.requests, "get", lambda *a, **kw: FakeResponse({"Valute": {}}))
    assert get_currency_rates(["USD"]) == []
    assert not any(key.startswith("currency_rates:") for key in no_cache)


# ---------- get_stock_prices ----------


def test_stock_prices_no_api_key(monkeypatch):
    monkeypatch.setattr(views, "_HAS_API_STOCK", False)
    monkeypatch.setattr(views, "file_cache_get", lambda key: None)
    assert get_stock_prices(["AAPL"]) == []


def test_stock_prices_success(no_cache, monkeypatch):
    monkeypatch.setattr(views, "_HAS_API_STOCK", True)
    monkeypatch.setattr(views, "API_STOCK_KEY", "test_key")

    def fake_get(url, params=None, timeout=None):
        return FakeResponse({"Global Quote": {"05. price": "150.1234"}})

    monkeypatch.setattr(views.requests, "get", fake_get)

    result = get_stock_prices(["AAPL", "MSFT"])
    assert result == [{"stock": "AAPL", "price": 150.12}, {"stock": "MSFT", "price": 150.12}]
    assert any(key.startswith("stock_prices:") for key in no_cache)


def test_stock_prices_missing_price_skipped(no_cache, monkeypatch):
    monkeypatch.setattr(views, "_HAS_API_STOCK", True)

    def fake_get(url, params=None, timeout=None):
        return FakeResponse({"Global Quote": {}})  # цены нет

    monkeypatch.setattr(views.requests, "get", fake_get)
    assert get_stock_prices(["AAPL"]) == []
    assert not any(key.startswith("stock_prices:") for key in no_cache)


def test_stock_prices_uses_cache(monkeypatch):
    cached = [{"stock": "AAPL", "price": 150.0}]
    monkeypatch.setattr(views, "file_cache_get", lambda key: cached)
    assert get_stock_prices(["AAPL"]) == cached


def test_stock_prices_api_failure(no_cache, monkeypatch):
    monkeypatch.setattr(views, "_HAS_API_STOCK", True)

    class Broken:
        def raise_for_status(self):
            raise views.requests.RequestException("boom")

    monkeypatch.setattr(views.requests, "get", lambda *a, **kw: Broken())
    assert get_stock_prices(["AAPL"]) == []


# ---------- get_period_range ----------


@pytest.mark.parametrize(
    "period,expected_start",
    [
        ("M", datetime(2021, 12, 1, 0, 0, 0)),
        ("W", datetime(2021, 12, 20, 0, 0, 0)),  # 20.12.2021 — понедельник
        ("Y", datetime(2021, 1, 1, 0, 0, 0)),
    ],
)
def test_get_period_range(period, expected_start):
    dt = datetime(2021, 12, 26, 15, 30)
    start, end = get_period_range(dt, period)
    assert start == expected_start
    assert end == datetime(2021, 12, 26, 23, 59, 59)


def test_get_period_range_all():
    start, end = get_period_range(datetime(2021, 12, 26), "ALL")
    assert start.year == 1
    assert end == datetime(2021, 12, 26, 23, 59, 59)


def test_get_period_range_unknown_falls_back_to_month():
    dt = datetime(2021, 12, 26, 15, 30)
    start, end = get_period_range(dt, "INVALID")
    assert start == datetime(2021, 12, 1, 0, 0, 0)
    assert end == datetime(2021, 12, 26, 23, 59, 59)


# ---------- main_page ----------


@pytest.fixture
def api_mocks(monkeypatch):
    """Мокает оба API и настройки для вызовов страниц."""
    monkeypatch.setattr(
        views, "load_user_settings",
        lambda: {"user_currencies": ["USD"], "user_stocks": ["AAPL"]},
    )
    monkeypatch.setattr(
        views, "get_currency_rates",
        lambda currencies: [{"currency": "USD", "rate": 75.0}],
    )
    monkeypatch.setattr(
        views, "get_stock_prices",
        lambda stocks: [{"stock": "AAPL", "price": 150.0}],
    )


@patch("src.views.datetime")
def test_main_page_structure(mock_dt, transactions, api_mocks):
    mock_dt.now.return_value = datetime(2021, 12, 26, 20, 0, 0)
    mock_dt.strptime = datetime.strptime
    data = json.loads(main_page("2021-12-26 20:00:00", transactions))

    assert data["greeting"] == "Добрый вечер"
    assert {c["last_digits"] for c in data["cards"]} == {"4589", "7123"}
    assert len(data["top_transactions"]) == 4  # всего 4 траты/поступления в декабре
    assert data["currency_rates"] == [{"currency": "USD", "rate": 75.0}]
    assert data["stock_prices"] == [{"stock": "AAPL", "price": 150.0}]


def test_main_page_cards_amounts(transactions, api_mocks):
    data = json.loads(main_page("2021-12-26 20:00:00", transactions))
    by_digits = {c["last_digits"]: c for c in data["cards"]}
    # *4589: -1000 + -2500; *7123: только -300 (поступление в счёт карты не идёт)
    assert by_digits["4589"]["total_spent"] == 3500.0
    assert by_digits["4589"]["cashback"] == 35.0
    assert by_digits["7123"]["total_spent"] == 300.0
    assert by_digits["7123"]["cashback"] == 3.0


def test_main_page_top_transactions(transactions, api_mocks):
    data = json.loads(main_page("2021-12-26 20:00:00", transactions))
    top = data["top_transactions"]
    # сортировка по модулю суммы по убыванию
    assert top[0]["amount"] == 50000.0
    assert top[1]["amount"] == -2500.0
    assert top[0]["date"] == "10.12.2021"


def test_main_page_empty_transactions(api_mocks):
    data = json.loads(main_page("2021-12-26 20:00:00", []))
    assert data["cards"] == []
    assert data["top_transactions"] == []


def test_main_page_ignores_missing_card_number(transactions, api_mocks):
    rows = transactions + [
        {"Дата операции": datetime(2021, 12, 20, 12, 0, 0),
         "Сумма платежа": -500.0, "Номер карты": "",
         "Категория": "Прочее", "Описание": "Без карты"},
    ]
    data = json.loads(main_page("2021-12-26 20:00:00", rows))
    # «Без карты» не создаёт карточки: суммы прежние
    by_digits = {c["last_digits"]: c for c in data["cards"]}
    assert by_digits["4589"]["total_spent"] == 3500.0


def test_main_page_ignores_non_numeric_amount(transactions, api_mocks):
    rows = transactions + [
        {"Дата операции": datetime(2021, 12, 21, 12, 0, 0),
         "Сумма платежа": "пусто", "Номер карты": "*9999",
         "Категория": "Прочее", "Описание": "Мусор"},
    ]
    data = json.loads(main_page("2021-12-26 20:00:00", rows))
    assert "9999" not in {c["last_digits"] for c in data["cards"]}


# ---------- events_page ----------


def test_events_month(transactions, api_mocks):
    data = json.loads(events_page("2021-12-26 20:00:00", transactions, "M"))

    assert data["expenses"]["total_amount"] == 3800  # 1000 + 2500 + 300
    assert data["income"]["total_amount"] == 50000
    cats = {item["category"]: item["amount"] for item in data["expenses"]["main"]}
    assert cats["Переводы"] == 2500
    assert cats["Супермаркеты"] == 1000
    assert data["expenses"]["transfers_and_cash"] == [
        {"category": "Переводы", "amount": 2500},
        {"category": "Наличные", "amount": 300},
    ]
    assert data["income"]["main"] == [{"category": "Зарплата", "amount": 50000}]


def test_events_week_excludes_other_days(transactions, api_mocks):
    """Пн 20.12.2021 — вс 26.12.2021: в набор не попадают операции до понедельника."""
    data = json.loads(events_page("2021-12-26 20:00:00", transactions, "W"))
    assert data["expenses"]["total_amount"] == 0
    assert data["income"]["total_amount"] == 0


def test_events_year_includes_november(transactions, api_mocks):
    data = json.loads(events_page("2021-12-26 20:00:00", transactions, "Y"))
    assert data["expenses"]["total_amount"] == 3800 + 750
    assert data["income"]["total_amount"] == 50000


def test_events_all_includes_everything(transactions, api_mocks):
    data = json.loads(events_page("2021-12-26 20:00:00", transactions, "ALL"))
    assert data["expenses"]["total_amount"] == 3800 + 750


def test_events_unknown_period_falls_back_to_month(transactions, api_mocks):
    data = json.loads(events_page("2021-12-26 20:00:00", transactions, "QUARTER"))
    assert data["expenses"]["total_amount"] == 3800


def test_events_top_seven_with_rest(api_mocks):
    """Больше семи категорий: восьмая и далее сворачиваются в «Остальное»."""
    rows = []
    amounts = [700.0, 600.0, 500.0, 400.0, 300.0, 200.0, 100.0, 50.0, 40.0]
    for i, amount in enumerate(amounts):
        rows.append({"Дата операции": datetime(2021, 12, i + 1, 12, 0, 0),
                     "Сумма платежа": -amount, "Категория": f"Категория {i}"})
    data = json.loads(events_page("2021-12-26 20:00:00", rows, "M"))

    main = data["expenses"]["main"]
    assert len(main) == 8  # 7 категорий + «Остальное»
    assert main[0] == {"category": "Категория 0", "amount": 700}
    assert main[-1] == {"category": "Остальное", "amount": 90}  # 50 + 40


def test_events_skips_non_numeric_amount(api_mocks):
    rows = [
        {"Дата операции": datetime(2021, 12, 1, 12, 0, 0),
         "Сумма платежа": -100.0, "Категория": "Супермаркеты"},
        {"Дата операции": datetime(2021, 12, 2, 12, 0, 0),
         "Сумма платежа": None, "Категория": "ЖКХ"},
    ]
    data = json.loads(events_page("2021-12-26 20:00:00", rows, "M"))
    assert data["expenses"]["total_amount"] == 100


def test_events_empty_period(api_mocks):
    data = json.loads(events_page("2022-05-05 12:00:00", [], "M"))
    assert data["expenses"] == {"total_amount": 0, "main": [], "transfers_and_cash": []}
    assert data["income"] == {"total_amount": 0, "main": []}


def test_events_accepts_dataframe(transactions, api_mocks):
    """events_page принимает и DataFrame, и список словарей — результат совпадает."""
    import pandas as pd

    df = pd.DataFrame(transactions)
    from_list = json.loads(events_page("2021-12-26 20:00:00", transactions, "M"))
    from_df = json.loads(events_page("2021-12-26 20:00:00", df, "M"))
    assert from_df["expenses"]["total_amount"] == from_list["expenses"]["total_amount"]
    assert from_df["expenses"]["total_amount"] == 3800
