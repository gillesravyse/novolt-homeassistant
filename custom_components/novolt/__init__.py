"""The Novolt integration: cloud-polling glue around the ``/v1`` read API."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NovoltClient
from .const import (
    CONF_BASE_URL,
    CONF_INSIGHTS_INTERVAL,
    CONF_SNAPSHOT_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_INSIGHTS_INTERVAL_S,
    DEFAULT_SNAPSHOT_INTERVAL_S,
)
from .coordinator import (
    NovoltConfigEntry,
    NovoltInsightsCoordinator,
    NovoltRuntimeData,
    NovoltSnapshotCoordinator,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NovoltConfigEntry) -> bool:
    """Set up one Novolt site from a config entry."""
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
