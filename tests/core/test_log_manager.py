import logging

from app.core.log_manager import configure_logging


def test_creates_log_file(tmp_path):
    path = configure_logging(log_dir=tmp_path, force=True)
    logging.getLogger("test").warning("Проверка журнала")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert path.exists()
    assert "Проверка журнала" in path.read_text(encoding="utf-8")


def test_masks_secret(tmp_path):
    path = configure_logging(log_dir=tmp_path, force=True)
    logging.getLogger("test").error("api_key=secret")
    for handler in logging.getLogger().handlers:
        handler.flush()
    content = path.read_text(encoding="utf-8")
    assert "secret" not in content
    assert "СКРЫТЫ" in content
