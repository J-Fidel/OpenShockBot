from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is invalid or missing."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} is required")
    return value


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _owner_ids() -> frozenset[int]:
    raw = os.getenv("BOT_OWNER_IDS", "")
    if not raw.strip():
        return frozenset()
    try:
        return frozenset(int(value.strip()) for value in raw.split(",") if value.strip())
    except ValueError as exc:
        raise ConfigurationError("BOT_OWNER_IDS must be comma-separated Discord user IDs") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    discord_bot_token: str
    openshock_token: str
    owner_ids: frozenset[int]
    database_path: Path
    openshock_api_base: str
    user_agent: str
    global_max_intensity: int
    global_max_duration_ms: int
    default_cooldown_seconds: float
    default_target_discord_id: int | None
    default_shocker_id: str | None
    reaction_shock_emoji: str
    reaction_vibrate_emoji: str
    reaction_sound_emoji: str

    @classmethod
    def from_env(cls) -> Settings:
        cooldown_raw = os.getenv("DEFAULT_COOLDOWN_SECONDS", "5")
        try:
            cooldown = float(cooldown_raw)
        except ValueError as exc:
            raise ConfigurationError("DEFAULT_COOLDOWN_SECONDS must be a number") from exc

        max_intensity = _int("GLOBAL_MAX_INTENSITY", 50)
        max_duration_ms = _int("GLOBAL_MAX_DURATION_MS", 5000)
        if not 1 <= max_intensity <= 100:
            raise ConfigurationError("GLOBAL_MAX_INTENSITY must be between 1 and 100")
        if not 300 <= max_duration_ms <= 65_535:
            raise ConfigurationError("GLOBAL_MAX_DURATION_MS must be between 300 and 65535")
        if cooldown < 0:
            raise ConfigurationError("DEFAULT_COOLDOWN_SECONDS cannot be negative")

        target_id = _optional_int("DEFAULT_TARGET_DISCORD_ID")
        shocker_id = os.getenv("DEFAULT_SHOCKER_ID", "").strip() or None
        if (target_id is None) != (shocker_id is None):
            raise ConfigurationError(
                "DEFAULT_TARGET_DISCORD_ID and DEFAULT_SHOCKER_ID must be set together"
            )

        return cls(
            discord_bot_token=_required("DISCORD_BOT_TOKEN"),
            openshock_token=_required("OPENSHOCK_TOKEN"),
            owner_ids=_owner_ids(),
            database_path=Path(os.getenv("DATABASE_PATH", "data/openshockbot.sqlite")),
            openshock_api_base=os.getenv("OPENSHOCK_API_BASE", "https://api.openshock.app").rstrip(
                "/"
            ),
            user_agent=os.getenv("USER_AGENT", "OpenShockBot/0.1.0").strip(),
            global_max_intensity=max_intensity,
            global_max_duration_ms=max_duration_ms,
            default_cooldown_seconds=cooldown,
            default_target_discord_id=target_id,
            default_shocker_id=shocker_id,
            reaction_shock_emoji=os.getenv("REACTION_SHOCK_EMOJI", "⚡"),
            reaction_vibrate_emoji=os.getenv("REACTION_VIBRATE_EMOJI", "🌊"),
            reaction_sound_emoji=os.getenv("REACTION_SOUND_EMOJI", "🔊"),
        )
