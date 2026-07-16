"""The Novolt integration: cloud-polling glue around the ``/v1`` read API."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .api import NovoltClient
from .const import (
    CONF_BASE_URL,
    CONF_INSIGHTS_INTERVAL,
    CONF_SNAPSHOT_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_INSIGHTS_INTERVAL_S,
    DEFAULT_SNAPSHOT_INTERVAL_S,
    DOMAIN,
)
from .coordinator import (
    NovoltConfigEntry,
    NovoltInsightsCoordinator,
    NovoltRuntimeData,
    NovoltSnapshotCoordinator,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CARDS_URL = "/novolt-cards/novolt-cards.js"
_CARDS_KEY = "novolt_cards_registered"


async def _async_register_cards(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace cards and load them on every dashboard.

    The integration ships its own cards (frontend/novolt-cards.js); registering
    them here means HACS-install + restart is all a user needs — no manual
    resource entry. Guarded so multiple config entries register once.
    """
    if hass.data.get(_CARDS_KEY):
        return
    hass.data[_CARDS_KEY] = True
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARDS_URL,
                str(Path(__file__).parent / "frontend" / "novolt-cards.js"),
                cache_headers=False,
            )
        ]
    )
    # The version query param busts browser caches on every release.
    integration = await async_get_integration(hass, DOMAIN)
    add_extra_js_url(hass, f"{CARDS_URL}?v={integration.version}")


async def async_setup_entry(hass: HomeAssistant, entry: NovoltConfigEntry) -> bool:
    """Set up one Novolt site from a config entry."""
    await _async_register_cards(hass)
    client = NovoltClient(
        entry.data[CONF_API_KEY],
        async_get_clientsession(hass),
        entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
    )
    snapshot = NovoltSnapshotCoordinator(
        hass,
        entry,
        client,
        entry.options.get(CONF_SNAPSHOT_INTERVAL, DEFAULT_SNAPSHOT_INTERVAL_S),
    )
    insights = NovoltInsightsCoordinator(
        hass,
        entry,
        client,
        entry.options.get(CONF_INSIGHTS_INTERVAL, DEFAULT_INSIGHTS_INTERVAL_S),
    )
    await snapshot.async_config_entry_first_refresh()
    await insights.async_config_entry_first_refresh()

    entry.runtime_data = NovoltRuntimeData(client=client, snapshot=snapshot, insights=insights)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: NovoltConfigEntry) -> None:
    """Reload on options change so the new poll intervals take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NovoltConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
