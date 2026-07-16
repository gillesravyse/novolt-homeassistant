"""Tests for the Novolt API client (no Home Assistant involved)."""

from novolt_api import (
    NovoltApiError,
    NovoltAuthError,
    NovoltClient,
    NovoltConnectionError,
)

import pytest
from aiohttp import web

KEY = "novolt_sk_test"


def _app(handler) -> web.Application:
    app = web.Application()
    app.router.add_get("/v1/snapshot", handler)
    app.router.add_get("/v1/history", handler)
    return app


async def test_snapshot_sends_bearer_key(aiohttp_client):
    seen: dict[str, str] = {}

    async def handler(request: web.Request) -> web.Response:
        seen["auth"] = request.headers.get("Authorization", "")
        return web.json_response({"pv_w": 1200.0, "live": True})

    client = await aiohttp_client(_app(handler))
    api = NovoltClient(KEY, client.session, base_url=str(client.make_url("")))
    data = await api.snapshot()
    assert data["pv_w"] == 1200.0
    assert seen["auth"] == f"Bearer {KEY}"


async def test_rejected_key_raises_auth_error(aiohttp_client):
    async def handler(request: web.Request) -> web.Response:
        return web.json_response({"detail": "Invalid or revoked API key."}, status=401)

    client = await aiohttp_client(_app(handler))
    api = NovoltClient(KEY, client.session, base_url=str(client.make_url("")))
    with pytest.raises(NovoltAuthError):
        await api.snapshot()


async def test_server_error_raises_api_error(aiohttp_client):
    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=500, text="boom")

    client = await aiohttp_client(_app(handler))
    api = NovoltClient(KEY, client.session, base_url=str(client.make_url("")))
    with pytest.raises(NovoltApiError):
        await api.snapshot()


async def test_non_object_json_raises_api_error(aiohttp_client):
    async def handler(request: web.Request) -> web.Response:
        return web.json_response([1, 2, 3])

    client = await aiohttp_client(_app(handler))
    api = NovoltClient(KEY, client.session, base_url=str(client.make_url("")))
    with pytest.raises(NovoltApiError):
        await api.snapshot()


async def test_history_passes_range(aiohttp_client):
    async def handler(request: web.Request) -> web.Response:
        return web.json_response({"range": request.query.get("range")})

    client = await aiohttp_client(_app(handler))
    api = NovoltClient(KEY, client.session, base_url=str(client.make_url("")))
    data = await api.history("7d")
    assert data["range"] == "7d"


async def test_unreachable_raises_connection_error(aiohttp_client):
    async def handler(request: web.Request) -> web.Response:
        return web.json_response({})

    client = await aiohttp_client(_app(handler))
    base = str(client.make_url(""))
    await client.server.close()
    api = NovoltClient(KEY, client.session, base_url=base)
    with pytest.raises(NovoltConnectionError):
        await api.snapshot()
