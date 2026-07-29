from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from .database import Database
from .models import ControlRequest, ControlResult, ControlType
from .openshock import OpenShockClient
from .policy import PolicyEngine, PolicyError


class CooldownError(PolicyError):
    pass


class ControlService:
    def __init__(
        self,
        database: Database,
        policy: PolicyEngine,
        client: OpenShockClient,
    ) -> None:
        self._database = database
        self._policy = policy
        self._client = client
        self._last_control: dict[tuple[int, int], float] = {}
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def execute(self, request: ControlRequest) -> ControlResult:
        try:
            resolved = await self._policy.evaluate(request)
            async with self._locks[request.target_id]:
                if request.action is not ControlType.STOP:
                    key = (request.actor_id, request.target_id)
                    last_control = self._last_control.get(key)
                    if last_control is not None:
                        remaining = (
                            last_control + resolved.target.cooldown_seconds - time.monotonic()
                        )
                        if remaining > 0:
                            raise CooldownError(
                                f"Please wait {remaining:.1f} seconds before controlling "
                                "this target again."
                            )

                if request.action is ControlType.STOP:
                    await self._client.stop(resolved.target.shocker_id)
                else:
                    await self._client.control(
                        shocker_id=resolved.target.shocker_id,
                        action=request.action,
                        intensity=resolved.intensity,
                        duration_ms=resolved.duration_ms,
                    )
                    self._last_control[(request.actor_id, request.target_id)] = time.monotonic()

            await self._database.log_control(
                request,
                outcome="sent",
                effective_intensity=resolved.intensity,
                effective_duration_ms=resolved.duration_ms,
            )
            return ControlResult(
                action=request.action,
                intensity=resolved.intensity,
                duration_ms=resolved.duration_ms,
                target_name=resolved.target.display_name or str(request.target_id),
            )
        except PolicyError as exc:
            await self._database.log_control(
                request,
                outcome="denied",
                detail=exc.public_message,
            )
            raise
        except Exception as exc:
            await self._database.log_control(
                request,
                outcome="failed",
                detail=str(exc)[:500],
            )
            raise
