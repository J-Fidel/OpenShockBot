from __future__ import annotations

from typing import Any

import aiohttp

from .models import ControlType


class OpenShockError(Exception):
    """Raised when the OpenShock API rejects or cannot complete a request."""


class OpenShockClient:
    def __init__(
        self,
        api_token: str,
        *,
        base_url: str = "https://api.openshock.app",
        user_agent: str = "OpenShockBot/0.1.0",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        if not user_agent:
            raise ValueError("A non-empty User-Agent is required by OpenShock")
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Open-Shock-Token": api_token,
            "User-Agent": user_agent,
            "Content-Type": "application/json",
        }
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def control(
        self,
        *,
        shocker_id: str,
        action: ControlType,
        intensity: int,
        duration_ms: int,
        exclusive: bool = True,
    ) -> None:
        payload: dict[str, Any] = {
            "shocks": [
                {
                    "id": shocker_id,
                    "type": action.value,
                    "intensity": intensity,
                    "duration": duration_ms,
                    "exclusive": exclusive,
                }
            ]
        }
        session = await self._get_session()
        try:
            async with session.post(
                f"{self._base_url}/2/shockers/control",
                headers=self._headers,
                json=payload,
            ) as response:
                if 200 <= response.status < 300:
                    return
                body = (await response.text()).strip()
                detail = body[:500] if body else response.reason
                raise OpenShockError(f"OpenShock returned HTTP {response.status}: {detail}")
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise OpenShockError(f"Could not reach OpenShock: {exc}") from exc

    async def stop(self, shocker_id: str) -> None:
        await self.control(
            shocker_id=shocker_id,
            action=ControlType.STOP,
            intensity=0,
            duration_ms=300,
            exclusive=True,
        )
