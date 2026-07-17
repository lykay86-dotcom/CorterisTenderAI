"""RM-136 UI-safe messages and disabled-provider check availability."""

from app.ui.tender_search_ui_controller import safe_manual_health_error_message


def test_worker_error_message_is_fixed_and_does_not_echo_raw_exception() -> None:
    sentinel = "RM136_UI_RAW_EXCEPTION_SENTINEL"
    message = safe_manual_health_error_message(RuntimeError(sentinel))
    assert sentinel not in message
    assert "RuntimeError" not in message
    assert message == "Проверка подключения завершилась безопасной ошибкой."
