"""Тесты файлового кэша API: чтение, запись, повреждённые файлы, директории."""
import json

from src.cache import file_cache_get, file_cache_load, file_cache_save

# ---------- file_cache_load ----------


def test_load_missing_file(tmp_path):
    assert file_cache_load(str(tmp_path / "nope.json")) == {}


def test_load_valid_file(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text(json.dumps({"key": {"timestamp": 1.0, "data": [1, 2]}}), encoding="utf-8")
    assert file_cache_load(str(path)) == {"key": {"timestamp": 1.0, "data": [1, 2]}}


def test_load_corrupted_file(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("{не json", encoding="utf-8")
    assert file_cache_load(str(path)) == {}


def test_load_non_dict_content(tmp_path):
    """Файл с валидным JSON, но не словарём (список, число) — считается пустым кэшем."""
    path = tmp_path / "cache.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert file_cache_load(str(path)) == {}


def test_load_empty_file(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("", encoding="utf-8")  # пустой файл: JSONDecodeError
    assert file_cache_load(str(path)) == {}


# ---------- file_cache_save ----------


def test_save_creates_directory(tmp_path):
    path = tmp_path / "deep" / "nested" / "cache.json"
    file_cache_save("rate", 75.5, str(path))
    assert path.exists()
    assert file_cache_get("rate", str(path)) == 75.5


def test_save_overwrites_preserving_other_keys(tmp_path):
    path = tmp_path / "cache.json"
    file_cache_save("a", 1, str(path))
    file_cache_save("b", 2, str(path))
    file_cache_save("a", 10, str(path))  # перезапись старого значения
    cache = file_cache_load(str(path))
    assert cache["a"]["data"] == 10
    assert cache["b"]["data"] == 2  # соседний ключ не затронут
    assert isinstance(cache["a"]["timestamp"], float)  # свежесть записана


def test_save_complex_data(tmp_path):
    path = tmp_path / "cache.json"
    data = [{"currency": "USD", "rate": 75.5}, {"currency": "EUR", "rate": 80.1}]
    file_cache_save("currency_rates:USD,EUR", data, str(path))
    assert file_cache_get("currency_rates:USD,EUR", str(path)) == data


def test_save_to_unwritable_path_logs_warning(tmp_path, capsys):
    """Файл вместо директории: os.makedirs падает, функция не бросает исключение."""
    blocker = tmp_path / "blocker"
    blocker.write_text("я файл, а не директория", encoding="utf-8")
    path = blocker / "cache.json"  # путь внутри файла — OSError гарантирован
    file_cache_save("key", "value", str(path))  # не должно упасть


# ---------- file_cache_get ----------


def test_get_missing_key(tmp_path):
    path = tmp_path / "cache.json"
    file_cache_save("a", 1, str(path))
    assert file_cache_get("b", str(path)) is None


def test_get_returns_data(tmp_path):
    path = tmp_path / "cache.json"
    file_cache_save("k", {"x": 42}, str(path))
    assert file_cache_get("k", str(path)) == {"x": 42}
