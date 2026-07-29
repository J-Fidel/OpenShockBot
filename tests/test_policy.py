from __future__ import annotations

from pathlib import Path

import pytest

from openshockbot.database import Database
from openshockbot.models import (
    AccessDecision,
    AccessMode,
    ControlRequest,
    ControlSource,
    ControlType,
)
from openshockbot.policy import PolicyEngine, PolicyError


@pytest.fixture
async def database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.sqlite")
    await database.connect()
    await database.upsert_target(
        100,
        "00000000-0000-0000-0000-000000000001",
        max_intensity=25,
        max_duration_ms=2000,
        cooldown_seconds=0,
    )
    yield database
    await database.close()


def request(*, actor: int = 200, action: ControlType = ControlType.SHOCK) -> ControlRequest:
    return ControlRequest(
        actor_id=actor,
        target_id=100,
        action=action,
        intensity=90,
        duration_ms=10_000,
        source=ControlSource.SLASH_COMMAND,
    )


async def test_policy_applies_lowest_safety_caps(database: Database) -> None:
    policy = PolicyEngine(
        database,
        global_max_intensity=50,
        global_max_duration_ms=5000,
    )

    resolved = await policy.evaluate(request())

    assert resolved.intensity == 25
    assert resolved.duration_ms == 2000


async def test_personal_block_rule_denies_control(database: Database) -> None:
    policy = PolicyEngine(
        database,
        global_max_intensity=50,
        global_max_duration_ms=5000,
    )
    await database.set_access_rule(100, 200, AccessDecision.BLOCK)

    with pytest.raises(PolicyError, match="blocked"):
        await policy.evaluate(request())


async def test_allowlist_requires_explicit_allow(database: Database) -> None:
    policy = PolicyEngine(
        database,
        global_max_intensity=50,
        global_max_duration_ms=5000,
    )
    await database.set_access_mode(100, AccessMode.ALLOWLIST)

    with pytest.raises(PolicyError, match="allowed users"):
        await policy.evaluate(request())

    await database.set_access_rule(100, 200, AccessDecision.ALLOW)
    assert (await policy.evaluate(request())).target.discord_user_id == 100


async def test_stop_bypasses_pause_and_access_block(database: Database) -> None:
    policy = PolicyEngine(
        database,
        global_max_intensity=50,
        global_max_duration_ms=5000,
    )
    await database.set_paused(100, True)
    await database.set_access_rule(100, 200, AccessDecision.BLOCK)

    resolved = await policy.evaluate(request(action=ControlType.STOP))

    assert resolved.intensity == 0
    assert resolved.duration_ms == 300
