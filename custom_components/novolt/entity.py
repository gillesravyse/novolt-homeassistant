"""Shared entity base for the Novolt integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import APP_URL, DOMAIN
from .coordinator import NovoltConfigEntry


class NovoltEntity(CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]]):
    """One Novolt site is one (service-type) device; every entity hangs off it."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        entry: NovoltConfigEntry,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Novolt",
            model="Energy platform",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=APP_URL,
        )
