"""Diagnostics for the Novolt integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import NovoltConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NovoltConfigEntry
) -> dict[str, Any]:
    """Dump both coordinators' latest payloads, key redacted."""
    data = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "snapshot": data.snapshot.data,
        "insights": data.insights.data,
    }
