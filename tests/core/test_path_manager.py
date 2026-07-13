from app.core.path_manager import PathManager


def test_ensure_directories(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTERIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CORTERIS_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("CORTERIS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("CORTERIS_CACHE_DIR", str(tmp_path / "cache"))
    PathManager.reset_instance()
    manager = PathManager(project_dir=tmp_path)
    paths = manager.ensure_directories()
    assert paths.data_dir.is_dir()
    assert paths.projects_dir.is_dir()
    assert paths.backups_dir.is_dir()
    assert paths.temp_dir.is_dir()


def test_writable_creates_parent(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTERIS_DATA_DIR", str(tmp_path / "data"))
    PathManager.reset_instance()
    manager = PathManager(project_dir=tmp_path)
    target = manager.writable("a", "b", "file.txt")
    assert target.parent.is_dir()


def test_resource_missing_raises(tmp_path):
    manager = PathManager(project_dir=tmp_path)
    try:
        manager.resource("missing.txt")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Ожидался FileNotFoundError")
