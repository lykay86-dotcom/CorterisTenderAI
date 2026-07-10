from app.core.version import APP_VERSION, version_string


def test_version():
    assert APP_VERSION == "1.5.1"
    assert "1.5.1" in version_string()
