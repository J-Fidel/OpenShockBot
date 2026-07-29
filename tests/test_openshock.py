from __future__ import annotations

from typing import Any

import pytest

from openshockbot.models import ControlType
from openshockbot.openshock import OpenShockClient, OpenShockError


class FakeResponse:
    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self.reason = "fake"
        self._body = body

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def text(self) -> str:
        return self._body


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.url = ""
        self.headers: dict[str, str] = {}
        self.payload: dict[str, Any] = {}

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> FakeResponse:
        self.url = url
        self.headers = headers
        self.payload = json
        return self.response


async def test_control_sends_v2_payload() -> None:
    session = FakeSession(FakeResponse(200))
    client = OpenShockClient("token", session=session)  # type: ignore[arg-type]

    await client.control(
        shocker_id="shocker-id",
        action=ControlType.VIBRATE,
        intensity=12,
        duration_ms=900,
    )

    assert session.url == "https://api.openshock.app/2/shockers/control"
    assert session.headers["Open-Shock-Token"] == "token"
    assert session.payload["shocks"][0] == {
        "id": "shocker-id",
        "type": "Vibrate",
        "intensity": 12,
        "duration": 900,
        "exclusive": True,
    }


async def test_control_surfaces_api_error() -> None:
    session = FakeSession(FakeResponse(403, "nope"))
    client = OpenShockClient("token", session=session)  # type: ignore[arg-type]

    with pytest.raises(OpenShockError, match="HTTP 403"):
        await client.stop("shocker-id")
