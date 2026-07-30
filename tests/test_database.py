from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from openshockbot.database import Database, LinkConflictError
from openshockbot.models import AccessMode, ControlType


async def test_new_target_gets_safe_per_reaction_defaults(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite")
    await database.connect()
    await database.upsert_target(
        100,
        "shocker-id",
        default_intensity=12,
        default_duration_ms=1500,
    )

    target = await database.get_target(100)

    assert target is not None
    assert target.reaction_settings[ControlType.SHOCK].enabled is False
    assert target.reaction_settings[ControlType.SHOCK].intensity == 1
    assert target.reaction_settings[ControlType.SHOCK].duration_ms == 300
    assert target.reaction_settings[ControlType.VIBRATE].enabled is True
    assert target.reaction_settings[ControlType.VIBRATE].intensity == 12
    assert target.reaction_settings[ControlType.VIBRATE].duration_ms == 1500
    assert target.reaction_settings[ControlType.SOUND].enabled is True
    assert target.reaction_settings[ControlType.SOUND].intensity == 12
    assert target.reaction_settings[ControlType.SOUND].duration_ms == 1500
    await database.close()


async def test_configuring_one_reaction_does_not_change_the_others(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite")
    await database.connect()
    await database.upsert_target(100, "shocker-id")

    updated = await database.configure_reaction(
        100,
        ControlType.SHOCK,
        enabled=True,
        intensity=7,
        duration_ms=600,
    )
    target = await database.get_target(100)

    assert updated is True
    assert target is not None
    assert target.reaction_settings[ControlType.SHOCK].enabled is True
    assert target.reaction_settings[ControlType.SHOCK].intensity == 7
    assert target.reaction_settings[ControlType.SHOCK].duration_ms == 600
    assert target.reaction_settings[ControlType.VIBRATE].intensity == 10
    assert target.reaction_settings[ControlType.SOUND].intensity == 10
    await database.close()


async def test_lowering_safety_caps_clamps_all_reaction_defaults(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite")
    await database.connect()
    await database.upsert_target(100, "shocker-id")

    await database.configure_target(
        100,
        max_intensity=5,
        max_duration_ms=600,
        cooldown_seconds=5,
    )
    target = await database.get_target(100)

    assert target is not None
    for reaction in target.reaction_settings.values():
        assert reaction.intensity <= 5
        assert reaction.duration_ms <= 600
    await database.close()


async def test_connect_migrates_legacy_reaction_defaults_safely(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE targets (
            discord_user_id TEXT PRIMARY KEY,
            shocker_id TEXT NOT NULL,
            display_name TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            paused INTEGER NOT NULL DEFAULT 0,
            reaction_enabled INTEGER NOT NULL DEFAULT 1,
            access_mode TEXT NOT NULL DEFAULT 'everyone',
            max_intensity INTEGER NOT NULL DEFAULT 25,
            max_duration_ms INTEGER NOT NULL DEFAULT 3000,
            default_intensity INTEGER NOT NULL DEFAULT 10,
            default_duration_ms INTEGER NOT NULL DEFAULT 1000,
            cooldown_seconds REAL NOT NULL DEFAULT 5
        );
        INSERT INTO targets (
            discord_user_id, shocker_id, reaction_enabled,
            default_intensity, default_duration_ms
        ) VALUES ('100', 'shocker-id', 1, 8, 700);
        """
    )
    connection.commit()
    connection.close()

    database = Database(path)
    await database.connect()
    target = await database.get_target(100)

    assert target is not None
    assert target.reaction_settings[ControlType.SOUND].enabled is True
    assert target.reaction_settings[ControlType.SOUND].intensity == 8
    assert target.reaction_settings[ControlType.VIBRATE].duration_ms == 700
    assert target.reaction_settings[ControlType.SHOCK].enabled is False
    assert target.reaction_settings[ControlType.SHOCK].intensity == 1
    assert target.reaction_settings[ControlType.SHOCK].duration_ms == 300
    await database.close()


async def test_pending_link_requires_acceptance_and_uses_safe_defaults(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite")
    await database.connect()
    shocker_id = "00000000-0000-0000-0000-000000000001"
    await database.stage_link(100, shocker_id, "Shared shocker", 900)

    assert await database.get_target(100) is None
    pending = await database.get_pending_link(100)
    assert pending is not None
    assert pending.shocker_name == "Shared shocker"

    await database.accept_pending_link(
        100,
        display_name="Target",
        max_intensity=25,
        max_duration_ms=3000,
        cooldown_seconds=5,
    )
    target = await database.get_target(100)

    assert target is not None
    assert target.paused is True
    assert target.access_mode is AccessMode.ALLOWLIST
    assert target.reaction_settings[ControlType.SHOCK].enabled is False
    assert await database.get_pending_link(100) is None
    await database.close()


async def test_assignment_conflicts_and_removal(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite")
    await database.connect()
    shocker_id = "00000000-0000-0000-0000-000000000001"
    await database.stage_link(100, shocker_id, "Shared shocker", 900)

    with pytest.raises(LinkConflictError, match="pending link request"):
        await database.stage_link(200, shocker_id, "Shared shocker", 900)

    removed_target, removed_pending = await database.remove_assignment(100)

    assert removed_target is False
    assert removed_pending is True
    assert await database.get_pending_link(100) is None
    await database.close()
