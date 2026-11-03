from datetime import datetime

import pytest

from emporio_agent import config


def test_store_now_uses_simulated_date_in_store_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "STORE_NOW", "2026-03-25T10:30")
    now = config.get_store_now()
    assert now == datetime(2026, 3, 25, 10, 30, tzinfo=config.STORE_TIMEZONE)


def test_store_now_falls_back_to_real_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "STORE_NOW", "")
    now = config.get_store_now()
    assert now.tzinfo == config.STORE_TIMEZONE
    assert now.year >= 2026


def test_all_data_files_exist() -> None:
    config.check_data_files()


def test_missing_api_key_fails_with_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        config.require_api_key()
