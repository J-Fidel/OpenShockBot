from __future__ import annotations

import pytest

from openshockbot.config import ConfigurationError, Settings


def test_settings_load_required_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "discord-secret")
    monkeypatch.setenv("OPENSHOCK_TOKEN", "openshock-secret")
    monkeypatch.setenv("BOT_OWNER_IDS", "123, 456")
    monkeypatch.setenv("GLOBAL_MAX_INTENSITY", "40")

    settings = Settings.from_env()

    assert settings.discord_bot_token == "discord-secret"
    assert settings.openshock_token == "openshock-secret"
    assert settings.owner_ids == frozenset({123, 456})
    assert settings.global_max_intensity == 40


def test_partial_default_mapping_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "discord-secret")
    monkeypatch.setenv("OPENSHOCK_TOKEN", "openshock-secret")
    monkeypatch.setenv("DEFAULT_TARGET_DISCORD_ID", "123")
    monkeypatch.delenv("DEFAULT_SHOCKER_ID", raising=False)

    with pytest.raises(ConfigurationError, match="must be set together"):
        Settings.from_env()
