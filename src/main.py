"""src/main.py Точка входа приложения анализа банковских операций."""
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from src import reports, services, utils, views

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "operations.xls"


def read_date(prompt: str) -> str:
    """Запрашивает дату, повторяя при некорректном вводе."""
    raw = ""
    valid = False
    while not valid:
        try:
            value = str(utils.parse_date(input(prompt)))
            raw = value.strip() if value is not None else ""
        except UnicodeDecodeError:
            print("Не распознал ввод — переключите раскладку на EN")
            continue
        if len(raw) == 10:
            raw += " 00:00:00"
        try:
            datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            valid = True
        except ValueError:
            print("Неверный формат. Пример: 2021-05-21")
    return raw


def read_int(prompt: str) -> int:
    """Запрашивает целое число, повторяя при некорректном вводе."""
    while True:
        try:
            return int(input(prompt).strip())
        except ValueError:
            print("Введите целое число")


def main() -> None:
    """Консольное меню приложения."""
    df = utils.read_transactions_excel(DATA_PATH)
    transactions: list[dict[str, Any]] = cast(
        list[dict[str, Any]], df.to_dict("records"))
    while True:
        print(
            "\nМеню:\n"
            "1. Главная (JSON-ответ)\n"
            "2. События (JSON-ответ)\n"
            "3. Выгодные категории кешбэка\n"
            "4. Инвесткопилка\n"
            "5. Простой поиск\n"
            "6. Поиск по телефонным номерам\n"
            "7. Переводы физическим лицам\n"
            "8. Траты по категории\n"
            "9. Траты по дням недели\n"
            "10. Траты в рабочий/выходной день\n"
            "0. Выход"
        )
        choice = input("Выберите пункт: ").strip()
        if choice == "0":
            break
        if choice == "1":
            print(views.main_page(read_date("Дата (YYYY-MM-DD HH:MM:SS): "), transactions))
        elif choice == "2":
            period = input("Период W/M/Y/ALL (Enter — месяц): ").strip().upper() or "M"
            print(views.events_page(read_date("Дата (YYYY-MM-DD): "), transactions, period))
        elif choice == "3":
            year = read_int("Год: ")
            month = read_int("Месяц (1-12): ")
            print(services.cashback_categories(transactions, year, month))
        elif choice == "4":
            print(services.investment_bank(read_date("Дата (YYYY-MM-DD): ")[:7], transactions,
                                           read_int("Порог (10/50/100): ")))
        elif choice == "5":
            print(services.simple_search(transactions, input("Строка поиска: ")))
        elif choice == "6":
            print(services.search_phone_numbers(transactions))
        elif choice == "7":
            print(services.transfers_to_individuals(transactions))
        elif choice == "8":
            date_in = input("Дата (необязательно, Enter — текущая): ").strip()
            print(reports.spending_by_category(df, input("Категория: "), date_in or None))
        elif choice == "9":
            date_in = input("Дата (необязательно, Enter — текущая): ").strip()
            print(reports.spending_by_weekday(df, date_in or None))
        elif choice == "10":
            date_in = input("Дата (необязательно, Enter — текущая): ").strip()
            print(reports.spending_by_workday_weekend(df, date_in or None))
        else:
            print("Некорректный пункт меню")


if __name__ == "__main__":
    main()
