from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ControlType(StrEnum):
    SHOCK = "Shock"
    VIBRATE = "Vibrate"
    SOUND = "Sound"
    STOP = "Stop"


class ControlSource(StrEnum):
    SLASH_COMMAND = "slash_command"
    REACTION = "reaction"
    BUTTON = "button"
    CONTEXT_MENU = "context_menu"


class AccessMode(StrEnum):
    EVERYONE = "everyone"
    ALLOWLIST = "allowlist"


class AccessDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class ReactionSetting:
    enabled: bool
    intensity: int
    duration_ms: int


@dataclass(frozen=True, slots=True)
class AccessibleShocker:
    shocker_id: str
    name: str
    source: str
    paused: bool


@dataclass(frozen=True, slots=True)
class PendingLink:
    target_discord_user_id: int
    shocker_id: str
    shocker_name: str
    requested_by_discord_user_id: int
    requested_at: str


@dataclass(frozen=True, slots=True)
class TargetAssignment:
    discord_user_id: int
    shocker_id: str
    display_name: str | None


@dataclass(frozen=True, slots=True)
class Target:
    discord_user_id: int
    shocker_id: str
    display_name: str | None
    enabled: bool
    paused: bool
    access_mode: AccessMode
    max_intensity: int
    max_duration_ms: int
    cooldown_seconds: float
    reaction_settings: dict[ControlType, ReactionSetting]


@dataclass(frozen=True, slots=True)
class ControlRequest:
    actor_id: int
    target_id: int
    action: ControlType
    intensity: int
    duration_ms: int
    source: ControlSource
    guild_id: int | None = None
    message_id: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedControl:
    request: ControlRequest
    target: Target
    intensity: int
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ControlResult:
    action: ControlType
    intensity: int
    duration_ms: int
    target_name: str
