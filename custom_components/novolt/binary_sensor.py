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
from .derive import find_charger, steers_anything
from .entity import NovoltEntity, charger_device_info


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
    # Does *Novolt* steer this site, or does it only watch. This reports what
    # the platform does; it is not a control, and Home Assistant cannot steer
    # anything through this integration at all — the API keys are read-only by
    # construction. An automation that assumes Novolt is dispatching the battery
    # while the site sits in shadow mode would be acting on a claim nobody made,
    # so the claim gets its own entity. ``read_only`` is the site-wide answer
    # (we write nowhere); the battery-specific one rides along as an attribute.
    #
    # Unavailable rather than ``off`` when the field is absent: a platform that
    # predates it says nothing about steering, and "nothing" must not be read
    # as "no".
    NovoltBinarySensorDescription(
        key="steering",
        translation_key="steering",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(steers_anything(d)),
        live_fn=lambda d: steers_anything(d) is not None,
        attributes_fn=lambda d: {"battery": d.get("steering")},
    ),
)

# State (not diagnostics) off the same fast loop.
SNAPSHOT_STATE_BINARY_SENSORS: tuple[NovoltBinarySensorDescription, ...] = (
    NovoltBinarySensorDescription(
        key="ev_charging",
        translation_key="ev_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda d: any(
            c.get("status") == "charging" for c in d.get("chargers") or []
        ),
        # Without fresh telemetry "not charging" would be a guess, not a fact.
        live_fn=lambda d: bool(d.get("live")) and bool(d.get("chargers")),
        exists_fn=lambda caps: bool(caps.get("ev", True)),
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


# ── per-charger binary sensors (one device per charger) ─────────────────────


@dataclass(frozen=True, kw_only=True)
class NovoltChargerBinarySensorDescription(BinarySensorEntityDescription):
    """Describes one per-charger binary sensor fed by ``snapshot.chargers[]``."""

    value_fn: Callable[[dict[str, Any]], bool]


CHARGER_BINARY_SENSORS: tuple[NovoltChargerBinarySensorDescription, ...] = (
    NovoltChargerBinarySensorDescription(
        key="online",
        translation_key="charger_online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        # "offline" is the API's word for a registered charger without a fresh
        # sample; everything else means it is reporting.
        value_fn=lambda c: c.get("status") != "offline",
    ),
    NovoltChargerBinarySensorDescription(
        key="charging",
        translation_key="charger_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda c: c.get("status") == "charging",
    ),
)


class NovoltChargerBinarySensor(NovoltEntity, BinarySensorEntity):
    """A binary sensor for one charger of the site."""

    entity_description: NovoltChargerBinarySensorDescription

    def __init__(
        self,
        entry: NovoltConfigEntry,
        charger: dict[str, Any],
        description: NovoltChargerBinarySensorDescription,
    ) -> None:
        charger_id = charger["id"]
        super().__init__(
            entry.runtime_data.snapshot,
            entry,
            f"charger_{charger_id}_{description.key}",
            device=charger_device_info(entry, charger),
        )
        self.entity_description = description
        self._charger_id = charger_id

    @property
    def _charger(self) -> dict[str, Any] | None:
        return find_charger(self.coordinator.data, self._charger_id)

    @property
    def available(self) -> bool:
        return (
            super().available
            and bool(self.coordinator.data.get("live"))
            and self._charger is not None
        )

    @property
    def is_on(self) -> bool:
        charger = self._charger
        return charger is not None and self.entity_description.value_fn(charger)


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
    snapshot = data.snapshot.data or {}
    caps = snapshot.get("capabilities") or {}
    entities: list[BinarySensorEntity] = [
        NovoltBinarySensor(data.snapshot, entry, description)
        for description in SNAPSHOT_BINARY_SENSORS + SNAPSHOT_STATE_BINARY_SENSORS
        if description.exists_fn(caps)
    ]
    entities.extend(
        NovoltBinarySensor(data.insights, entry, description)
        for description in INSIGHTS_BINARY_SENSORS
        if description.exists_fn(caps)
    )
    # Per-charger devices follow the site's EV capability, exactly like the
    # site-level EV entities do.
    if caps.get("ev", True):
        for charger in snapshot.get("chargers") or []:
            if not charger.get("id"):
                continue
            entities.extend(
                NovoltChargerBinarySensor(entry, charger, description)
                for description in CHARGER_BINARY_SENSORS
            )
    async_add_entities(entities)
