"""Config flow for the Novolt integration."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NovoltAuthError, NovoltClient, NovoltConnectionError
from .const import (
    CONF_BASE_URL,
    CONF_INSIGHTS_INTERVAL,
    CONF_SNAPSHOT_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_INSIGHTS_INTERVAL_S,
    DEFAULT_SNAPSHOT_INTERVAL_S,
    DOMAIN,
    MAX_INTERVAL_S,
    MIN_INSIGHTS_INTERVAL_S,
    MIN_SNAPSHOT_INTERVAL_S,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


async def _validate(hass: HomeAssistant, api_key: str, base_url: str) -> dict[str, Any]:
    """Probe the API with the key; returns the snapshot on success."""
    client = NovoltClient(api_key.strip(), async_get_clientsession(hass), base_url)
    return await client.snapshot()


def _title(snapshot: dict[str, Any]) -> str:
    """The site's own name, so two sites are two readable devices.

    Everything on the site device is named after the entry, and a second entry
    titled "Novolt" as well would give a two-site household two identically
    named devices with nothing to tell them apart. Existing entries keep the
    title they have — renaming someone's device on an update is not an upgrade.
    """
    name = snapshot.get("site_name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "Novolt"


def _unique_id(api_key: str, snapshot: dict[str, Any]) -> str:
    """Stable identity for the entry.

    Prefers the site id when the API exposes it (additive ``/v1`` field);
    otherwise falls back to a digest of the key, which still guards against
    adding the same key twice.
    """
    site_id = snapshot.get("site_id")
    if isinstance(site_id, str) and site_id:
        return site_id
    return hashlib.sha256(api_key.strip().encode()).hexdigest()[:16]


class NovoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Novolt config flow (user setup + reauth)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initial setup: API key (+ optional non-default base URL)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            base_url = (user_input.get(CONF_BASE_URL) or DEFAULT_BASE_URL).strip()
            try:
                snapshot = await _validate(self.hass, api_key, base_url)
            except NovoltAuthError:
                errors["base"] = "invalid_auth"
            except NovoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 — surface as a form error, not a trace
                _LOGGER.exception("Unexpected error validating Novolt API key")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(_unique_id(api_key, snapshot))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=_title(snapshot),
                    data={CONF_API_KEY: api_key, CONF_BASE_URL: base_url},
                )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """The key was revoked/rotated: ask for a fresh one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the replacement key and update the existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            base_url = entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)
            try:
                await _validate(self.hass, api_key, base_url)
            except NovoltAuthError:
                errors["base"] = "invalid_auth"
            except NovoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Novolt API key")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> NovoltOptionsFlow:
        """Expose the poll-interval options."""
        return NovoltOptionsFlow()


class NovoltOptionsFlow(OptionsFlow):
    """Tune the two poll intervals."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SNAPSHOT_INTERVAL,
                    default=options.get(CONF_SNAPSHOT_INTERVAL, DEFAULT_SNAPSHOT_INTERVAL_S),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SNAPSHOT_INTERVAL_S, max=MAX_INTERVAL_S)),
                vol.Required(
                    CONF_INSIGHTS_INTERVAL,
                    default=options.get(CONF_INSIGHTS_INTERVAL, DEFAULT_INSIGHTS_INTERVAL_S),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_INSIGHTS_INTERVAL_S, max=MAX_INTERVAL_S)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
