from __future__ import annotations

from .database import Database
from .models import (
    AccessDecision,
    AccessMode,
    ControlRequest,
    ControlSource,
    ControlType,
    ResolvedControl,
)


class PolicyError(Exception):
    def __init__(self, public_message: str) -> None:
        super().__init__(public_message)
        self.public_message = public_message


class PolicyEngine:
    def __init__(
        self,
        database: Database,
        *,
        global_max_intensity: int,
        global_max_duration_ms: int,
    ) -> None:
        self._database = database
        self._global_max_intensity = global_max_intensity
        self._global_max_duration_ms = global_max_duration_ms

    async def evaluate(self, request: ControlRequest) -> ResolvedControl:
        target = await self._database.get_target(request.target_id)
        if target is None:
            raise PolicyError("That Discord user is not linked to an OpenShock shocker.")
        if not target.enabled:
            raise PolicyError("That target is disabled.")
        if target.paused and request.action is not ControlType.STOP:
            raise PolicyError("That target is currently paused.")
        if request.source is ControlSource.REACTION and not target.reaction_enabled:
            raise PolicyError("Reaction controls are disabled for that target.")

        if request.action is ControlType.STOP:
            return ResolvedControl(
                request=request,
                target=target,
                intensity=0,
                duration_ms=300,
            )

        if request.actor_id != request.target_id:
            decision = await self._database.get_access_decision(request.target_id, request.actor_id)
            if decision is AccessDecision.BLOCK:
                raise PolicyError("You are blocked from controlling that target.")
            if target.access_mode is AccessMode.ALLOWLIST and decision is not AccessDecision.ALLOW:
                raise PolicyError("That target only accepts controls from allowed users.")

        if not 1 <= request.intensity <= 100:
            raise PolicyError("Intensity must be between 1 and 100.")
        if not 300 <= request.duration_ms <= 65_535:
            raise PolicyError("Duration must be between 0.3 and 65.535 seconds.")

        intensity = min(
            request.intensity,
            target.max_intensity,
            self._global_max_intensity,
        )
        duration_ms = min(
            request.duration_ms,
            target.max_duration_ms,
            self._global_max_duration_ms,
        )
        return ResolvedControl(
            request=request,
            target=target,
            intensity=intensity,
            duration_ms=duration_ms,
        )
