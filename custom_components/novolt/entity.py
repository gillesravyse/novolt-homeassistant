"""Shared entity base for the Novolt integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import APP_URL, DOMAIN
from .coordinator import NovoltConfigEntry


def site_device_info(entry: NovoltConfigEntry) -> DeviceInfo:
    """The site itself: one service-type device per config entry."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Novolt",
        model="Energy platform",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=APP_URL,
    )


def charger_device_info(entry: NovoltConfigEntry, charger: dict[str, Any]) -> DeviceInfo:
    """A charger is its own device under the site, named as in the Novolt app.

    Giving each charger its own device is what makes a two-charger site
    readable: the entities are ``Lader links Power`` / ``Lader rechts Power``
    instead of two identically named sensors on the site device.
    """
    charger_id = charger["id"]
    vendor = (charger.get("vendor") or "").strip()
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_charger_{charger_id}")},
        name=charger.get("name") or charger_id,
        manufacturer=vendor.title() or "Novolt",
        model="EV charger",
        via_device=(DOMAIN, entry.entry_id),
        configuration_url=APP_URL,
    )


class NovoltEntity(CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]]):
    """One Novolt site is one (service-type) device; every entity hangs off it."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        entry: NovoltConfigEntry,
        key: str,
        device: DeviceInfo | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = device or site_device_info(entry)
