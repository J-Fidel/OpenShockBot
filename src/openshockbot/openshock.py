from __future__ import annotations

from typing import Any

import aiohttp

from .models import AccessibleShocker, ControlType


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

    async def _get_json(self, path: str) -> Any:
        session = await self._get_session()
        try:
            async with session.get(
                f"{self._base_url}{path}",
                headers=self._headers,
            ) as response:
                if 200 <= response.status < 300:
                    try:
                        return await response.json(content_type=None)
                    except (ValueError, TypeError) as exc:
                        raise OpenShockError("OpenShock returned invalid JSON") from exc
                body = (await response.text()).strip()
                detail = body[:500] if body else response.reason
                raise OpenShockError(f"OpenShock returned HTTP {response.status}: {detail}")
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise OpenShockError(f"Could not reach OpenShock: {exc}") from exc

    async def list_accessible_shockers(self) -> list[AccessibleShocker]:
        owned_payload = await self._get_json("/1/shockers/own")
        shared_payload = await self._get_json("/1/shockers/shared")
        shockers: dict[str, AccessibleShocker] = {}

        owned_data = owned_payload.get("data") if isinstance(owned_payload, dict) else None
        if isinstance(owned_data, list):
            for device in owned_data:
                if not isinstance(device, dict):
                    continue
                device_shockers = device.get("shockers")
                if not isinstance(device_shockers, list):
                    continue
                for shocker in device_shockers:
                    parsed = self._parse_shocker(shocker, source="owned")
                    if parsed is not None:
                        shockers[parsed.shocker_id] = parsed

        shared_data = shared_payload.get("data") if isinstance(shared_payload, dict) else None
        if isinstance(shared_data, list):
            for owner in shared_data:
                if not isinstance(owner, dict):
                    continue
                devices = owner.get("devices")
                if not isinstance(devices, list):
                    continue
                for device in devices:
                    if not isinstance(device, dict):
                        continue
                    device_shockers = device.get("shockers")
                    if not isinstance(device_shockers, list):
                        continue
                    for shocker in device_shockers:
                        parsed = self._parse_shocker(shocker, source="shared")
                        if parsed is not None:
                            shockers.setdefault(parsed.shocker_id, parsed)

        return sorted(
            shockers.values(), key=lambda shocker: (shocker.name.lower(), shocker.shocker_id)
        )

    @staticmethod
    def _parse_shocker(value: object, *, source: str) -> AccessibleShocker | None:
        if not isinstance(value, dict):
            return None
        shocker_id = value.get("id")
        name = value.get("name")
        if not isinstance(shocker_id, str) or not isinstance(name, str):
            return None
        return AccessibleShocker(
            shocker_id=shocker_id,
            name=name,
            source=source,
            paused=bool(value.get("isPaused", False)),
        )

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
