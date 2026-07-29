from __future__ import annotations

from pathlib import Path

import pytest

from openshockbot.database import Database
from openshockbot.models import ControlRequest, ControlSource, ControlType
from openshockbot.policy import PolicyEngine
from openshockbot.service import ControlService, CooldownError


class FakeOpenShockClient:
    def __init__(self) -> None:
        self.controls: list[dict[str, object]] = []
        self.stops: list[str] = []

    async def control(
        self,
        *,
        shocker_id: str,
        action: ControlType,
        intensity: int,
        duration_ms: int,
        exclusive: bool = True,
    ) -> None:
        self.controls.append(
            {
                "shocker_id": shocker_id,
                "action": action,
                "intensity": intensity,
                "duration_ms": duration_ms,
                "exclusive": exclusive,
            }
        )

    async def stop(self, shocker_id: str) -> None:
        self.stops.append(shocker_id)


@pytest.fixture
async def database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.sqlite")
    await database.connect()
    await database.upsert_target(
        100,
        "shocker-id",
        display_name="Target",
        max_intensity=25,
        max_duration_ms=2000,
        cooldown_seconds=60,
    )
    yield database
    await database.close()


def request(action: ControlType = ControlType.SHOCK) -> ControlRequest:
    return ControlRequest(
        actor_id=200,
        target_id=100,
        action=action,
        intensity=90,
        duration_ms=10_000,
        source=ControlSource.SLASH_COMMAND,
    )


async def test_service_sends_effective_values_and_audits(database: Database) -> None:
    fake = FakeOpenShockClient()
    service = ControlService(
        database,
        PolicyEngine(database, global_max_intensity=50, global_max_duration_ms=5000),
        fake,  # type: ignore[arg-type]
    )

    result = await service.execute(request())
    audit = await database.recent_audit(100)

    assert result.intensity == 25
    assert result.duration_ms == 2000
    assert fake.controls[0]["intensity"] == 25
    assert audit[0]["outcome"] == "sent"
    assert audit[0]["effective_intensity"] == 25


async def test_first_control_is_allowed_during_low_system_uptime(
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("openshockbot.service.time.monotonic", lambda: 1.0)
    fake = FakeOpenShockClient()
    service = ControlService(
        database,
        PolicyEngine(database, global_max_intensity=50, global_max_duration_ms=5000),
        fake,  # type: ignore[arg-type]
    )

    await service.execute(request())

    assert len(fake.controls) == 1


async def test_service_enforces_cooldown_but_never_blocks_stop(database: Database) -> None:
    fake = FakeOpenShockClient()
    service = ControlService(
        database,
        PolicyEngine(database, global_max_intensity=50, global_max_duration_ms=5000),
        fake,  # type: ignore[arg-type]
    )

    await service.execute(request())
    with pytest.raises(CooldownError):
        await service.execute(request())

    await service.execute(request(ControlType.STOP))
    assert fake.stops == ["shocker-id"]
