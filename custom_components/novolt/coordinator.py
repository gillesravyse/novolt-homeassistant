"""Data update coordinators for the Novolt integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NovoltApiError, NovoltAuthError, NovoltClient

_LOGGER = logging.getLogger(__name__)

type NovoltConfigEntry = ConfigEntry[NovoltRuntimeData]


@dataclass
class NovoltRuntimeData:
    """Everything a platform needs, hung off ``entry.runtime_data``."""

    client: NovoltClient
    snapshot: NovoltSnapshotCoordinator
    insights: NovoltInsightsCoordinator


class NovoltSnapshotCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fast loop: the live power snapshot (``/v1/snapshot``)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NovoltConfigEntry,
        client: NovoltClient,
        interval_s: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.title} snapshot",
            update_interval=timedelta(seconds=interval_s),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.snapshot()
        except NovoltAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NovoltApiError as err:
            raise UpdateFailed(str(err)) from err


class NovoltInsightsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Slow loop: prices, the dispatch plan and the 24 h energy aggregates.

    These only change per quarter-hour/publication, so they poll on their own
    cadence instead of riding the snapshot loop. The three calls run
    concurrently; one combined dict keeps a single source of truth per tick.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NovoltConfigEntry,
        client: NovoltClient,
        interval_s: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.title} insights",
            update_interval=timedelta(seconds=interval_s),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            prices, plan, today = await asyncio.gather(
                self.client.prices(), self.client.plan(), self.client.today()
            )
        except NovoltAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NovoltApiError as err:
            raise UpdateFailed(str(err)) from err
        return {"prices": prices, "plan": plan, "today": today}
