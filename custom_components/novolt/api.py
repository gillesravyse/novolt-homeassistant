"""Async client for the Novolt public read-only API (``/v1``).

Deliberately free of Home Assistant imports so it can be extracted into a
standalone PyPI package (``pynovolt``) unchanged. The ``/v1`` contract is
frozen additive-only server-side; this client passes responses through as
dicts and leaves interpretation to the caller.
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

DEFAULT_BASE_URL = "https://api.novolt.be"
DEFAULT_TIMEOUT_S = 15.0

API_KEY_PREFIX = "novolt_sk_"


class NovoltApiError(Exception):
    """The API answered with an unexpected error."""


class NovoltAuthError(NovoltApiError):
    """The API key is missing, invalid or revoked (HTTP 401/403)."""


class NovoltConnectionError(NovoltApiError):
    """The API could not be reached (network error or timeout)."""


class NovoltClient:
    """Thin async wrapper around the five ``/v1`` read endpoints."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._api_key = api_key
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout_s)

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with self._session.get(
                url, headers=headers, params=params, timeout=self._timeout
            ) as resp:
                if resp.status in (401, 403):
                    raise NovoltAuthError(f"API key rejected ({resp.status})")
                if resp.status >= 400:
                    body = (await resp.text())[:200]
                    raise NovoltApiError(f"GET {path} failed ({resp.status}): {body}")
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise NovoltConnectionError(f"Cannot reach Novolt API: {err}") from err
        if not isinstance(data, dict):
            raise NovoltApiError(f"GET {path} returned non-object JSON")
        return data

    async def snapshot(self) -> dict[str, Any]:
        """Live power snapshot + current price for the key's site."""
        return await self._get("/v1/snapshot")

    async def plan(self) -> dict[str, Any]:
        """Battery dispatch decision + 24h schedule + EV plan."""
        return await self._get("/v1/plan")

    async def prices(self) -> dict[str, Any]:
        """Day-ahead dynamic prices (retail + injection) for the site tariff."""
        return await self._get("/v1/prices")

    async def today(self) -> dict[str, Any]:
        """Energy aggregates over the trailing 24 h window."""
        return await self._get("/v1/today")

    async def history(self, range_key: str = "24h") -> dict[str, Any]:
        """Power history (pv/grid/battery/house) for the site."""
        return await self._get("/v1/history", params={"range": range_key})
