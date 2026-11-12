# test_reports.py

"""Тесты отчётов и декоратора сохранения."""
import os

import pytest

from src.reports import save_to_file, spending_by_category, spending_by_weekday, spending_by_workday_weekend


@pytest.fixture(autouse=True)
def _tmp_reports_dir(tmp_path, monkeypatch):
    """Все отчёты пишутся во временную директорию, а не в корень проекта."""
    monkeypatch.chdir(tmp_path)


def test_spending_by_category(df):
    result = spending_by_category(df, "Супермаркеты", "26.12.2021")
    assert result == {"category": "Супермаркеты", "total": 6351.23}
    assert os.path.exists("reports/spending_by_category_report.json")


def test_spending_by_category_default_date(df):
    result = spending_by_category(df, "ЖКХ")
    assert result["category"] == "ЖКХ"
    assert result["total"] == 0.0  # данные 2021 года вне окна трёх месяцев от текущей даты


def test_spending_by_weekday(df):
    result = spending_by_weekday(df, "20.12.2021")
    assert result["Понедельник"] == 774.67
    assert result["Среда"] == 1169.75
    assert result["Четверг"] == 725.0
    assert result["Пятница"] == 1412.41
    assert result["Суббота"] == 1250.0
    assert result["Воскресенье"] == 3966.61
    assert "Вторник" not in result  # в окне 20.09-20.12 трат во вторник нет


def test_spending_by_workday_weekend(df):
    result = spending_by_workday_weekend(df, "20.12.2021")
    assert result == {"рабочий": 1057.52, "выходной": 3061.07}


def test_decorator_with_custom_filename(df):
    @save_to_file("custom_test_report.json")
    def custom_report(dataframe):
        return {"total": 1.0}

    custom_report(df)
    assert os.path.exists("reports/custom_test_report.json")


def test_decorator_without_filename(df):
    @save_to_file()
    def another_report(dataframe):
        return {"sum": 2.0}

    another_report(df)
    assert os.path.exists("reports/another_report_report.json")
