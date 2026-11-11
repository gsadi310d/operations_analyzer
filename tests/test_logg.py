"""Тесты настройки логгера."""
import logging

from src.logg import setup_logger


def test_setup_logger_creates_handlers(tmp_path):
    log_file = tmp_path / "logs" / "test.log"
    logger = setup_logger("test_view_1", str(log_file))

    # создана директория и файл-хендлер
    assert log_file.parent.exists()
    assert logger.level == logging.DEBUG
    assert logger.propagate is False
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.FileHandler)


def test_setup_logger_does_not_duplicate_handlers(tmp_path):
    """Повторный вызов с тем же именем не добавляет второй хендлер."""
    log_file = tmp_path / "test.log"
    first = setup_logger("test_view_2", str(log_file))
    second = setup_logger("test_view_2", str(log_file))

    assert first is second
    assert len(first.handlers) == 1  # ← эта проверка выполняет строку 14


def test_setup_logger_writes_message(tmp_path):
    log_file = tmp_path / "test.log"
    logger = setup_logger("test_view_3", str(log_file))
    logger.error("тестовое сообщение")

    content = log_file.read_text(encoding="utf-8")
    assert "тестовое сообщение" in content
    assert "ERROR" in content
