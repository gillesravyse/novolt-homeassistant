"""Binary sensors for the Novolt integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .coordinator import NovoltConfigEntry
from .entity import NovoltEntity


@dataclass(frozen=True, kw_only=True)
class NovoltBinarySensorDescription(BinarySensorEntityDescription):
    """Describes one Novolt binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool]
    live_fn: Callable[[dict[str, Any]], bool] = lambda data: True
    exists_fn: Callable[[dict[str, Any]], bool] = lambda caps: True
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None


# Diagnostics ride the fast loop: they *are* the honesty flags, so they stay
# available even when the flags are False.
SNAPSHOT_BINARY_SENSORS: tuple[NovoltBinarySensorDescription, ...] = (
    NovoltBinarySensorDescription(
        key="data_live",
        translation_key="data_live",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(d.get("live")),
    ),
    NovoltBinarySensorDescription(
        key="prices_live",
        translation_key="prices_live",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(d.get("prices_live")),
    ),
)

INSIGHTS_BINARY_SENSORS: tuple[NovoltBinarySensorDescription, ...] = (
    NovoltBinarySensorDescription(
        key="ev_cheap_now",
        translation_key="ev_cheap_now",
        value_fn=lambda d: bool(((d.get("plan") or {}).get("ev") or {}).get("cheap_now")),
        # Without a real price curve there is no plan — unavailable, not False.
        live_fn=lambda d: bool((d.get("plan") or {}).get("prices_live")),
        exists_fn=lambda caps: bool(caps.get("ev", True)),
        attributes_fn=lambda d: {
            "schedule": ((d.get("plan") or {}).get("ev") or {}).get("schedule", [])
        },
    ),
)


class NovoltBinarySensor(NovoltEntity, BinarySensorEntity):
    """A Novolt binary sensor on either coordinator."""

    entity_description: NovoltBinarySensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        entry: NovoltConfigEntry,
        description: NovoltBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.live_fn(self.coordinator.data)

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NovoltConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Novolt binary sensors."""
    data = entry.runtime_data
    caps = (data.snapshot.data or {}).get("capabilities") or {}
    entities = [
        NovoltBinarySensor(data.snapshot, entry, description)
        for description in SNAPSHOT_BINARY_SENSORS
        if description.exists_fn(caps)
    ]
    entities.extend(
        NovoltBinarySensor(data.insights, entry, description)
        for description in INSIGHTS_BINARY_SENSORS
        if description.exists_fn(caps)
    )
    async_add_entities(entities)
