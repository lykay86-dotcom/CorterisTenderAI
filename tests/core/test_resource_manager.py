from pathlib import Path

import pytest

from app.core.path_manager import PathManager
from app.core.resource_manager import ResourceManager


def test_inspect_hash(tmp_path):
    file = tmp_path / "x.txt"
    file.write_text("abc", encoding="utf-8")
    info = ResourceManager.inspect(file)
    assert info.size == 3
    assert len(info.sha256) == 64


def test_copy_user_template(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTERIS_DATA_DIR", str(tmp_path / "data"))
    PathManager.reset_instance()
    source = tmp_path / "source.docx"
    source.write_bytes(b"docx")
    manager = ResourceManager(PathManager(project_dir=tmp_path))
    target = manager.copy_user_template(source, "offer.docx")
    assert target.read_bytes() == b"docx"


def test_reject_non_docx(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("x")
    manager = ResourceManager(PathManager(project_dir=tmp_path))
    with pytest.raises(ValueError):
        manager.copy_user_template(source, "x.txt")
