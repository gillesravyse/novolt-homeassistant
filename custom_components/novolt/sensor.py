"""Sensors for the Novolt integration.

Honest about data availability throughout (a stale edge or a missing price
curve makes an entity ``unavailable`` — never a zero presented as a
measurement):

* snapshot sensors — live powers, SOC and the current tariff prices (fast loop)
* per-charger sensors — one device per charging station, off the same fast loop
* per-source PV sensors — one entity per inverter on a multi-inverter site
* energy sensors — cumulative kWh counters integrated client-side from the
  live powers, restored across restarts; these feed the Energy Dashboard
* insights sensors (slow loop) — the API's trailing-24h aggregates including
  the euros saved and spent, the dispatch decision, the 24 h forecast
  trajectories, the EV charge quota and the plan's grid peak

The payload logic behind the values lives in :mod:`.derive`, free of Home
Assistant imports so it can be tested without one.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import BATTERY_COMMANDS, ENERGY_MAX_GAP_S
from .coordinator import NovoltConfigEntry
from .derive import (
    CHARGER_STATUSES,
    charger_status,
    ev_hours,
    ev_hours_attributes,
    ev_km,
    find_charger,
    find_pv_source,
    forecast_live,
    house_no_ev,
    peak_shaving_attributes,
    plan_series,
    plan_slot_value,
)
from .entity import NovoltEntity, charger_device_info

PRICE_UNIT = "EUR/kWh"
CURRENCY_EUR = "EUR"


def _snapshot_live(data: dict[str, Any]) -> bool:
    return bool(data.get("live"))


def _prices_live(data: dict[str, Any]) -> bool:
    return bool(data.get("prices_live"))


def _always(_: dict[str, Any]) -> bool:
    return True


def _has_battery(caps: dict[str, Any]) -> bool:
    return bool(caps.get("battery", True))


def _has_solar(caps: dict[str, Any]) -> bool:
    return bool(caps.get("solar", True))


def _has_ev(caps: dict[str, Any]) -> bool:
    return bool(caps.get("ev", True))


# ── snapshot sensors (fast loop) ────────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class NovoltSnapshotSensorDescription(SensorEntityDescription):
    """Describes one sensor fed by the live snapshot."""

    value_fn: Callable[[dict[str, Any]], StateType]
    live_fn: Callable[[dict[str, Any]], bool] = _snapshot_live
    exists_fn: Callable[[dict[str, Any]], bool] = lambda caps: True
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None


SNAPSHOT_SENSORS: tuple[NovoltSnapshotSensorDescription, ...] = (
    NovoltSnapshotSensorDescription(
        key="pv_power",
        translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.get("pv_w"),
        exists_fn=_has_solar,
        # The per-inverter split behind the sum. Also exposed as one entity per
        # source (see NovoltPvSourceSensor); the attribute is the fallback that
        # survives a restart taken while the edge was offline.
        attributes_fn=lambda d: {"sources": d.get("pv_sources", [])},
    ),
    NovoltSnapshotSensorDescription(
        key="grid_power",
        translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.get("grid_net_w"),
    ),
    NovoltSnapshotSensorDescription(
        key="grid_import_power",
        translation_key="grid_import_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.get("grid_import_w"),
    ),
    NovoltSnapshotSensorDescription(
        key="grid_export_power",
        translation_key="grid_export_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.get("grid_export_w"),
    ),
    NovoltSnapshotSensorDescription(
        key="house_power",
        translation_key="house_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.get("house_load_w"),
    ),
    NovoltSnapshotSensorDescription(
        key="house_power_no_ev",
        translation_key="house_power_no_ev",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        # The baseline load: house minus the cars. Only meaningful on a site
        # with chargers — without them it would duplicate house_power.
        value_fn=house_no_ev,
        exists_fn=_has_ev,
    ),
    NovoltSnapshotSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.get("battery_w"),
        exists_fn=_has_battery,
    ),
    NovoltSnapshotSensorDescription(
        key="battery_soc",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.get("battery_soc_pct"),
        exists_fn=_has_battery,
    ),
    NovoltSnapshotSensorDescription(
        key="ev_power",
        translation_key="ev_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.get("ev_w"),
        exists_fn=_has_ev,
        attributes_fn=lambda d: {"chargers": d.get("chargers", [])},
    ),
)

# The current tariff prices ride the fast loop (so an hour rollover shows up
# quickly); the day-ahead curve attributes come from the insights loop.
PRICE_SENSORS: tuple[NovoltSnapshotSensorDescription, ...] = (
    NovoltSnapshotSensorDescription(
        key="price_current",
        translation_key="price_current",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=4,
        value_fn=lambda d: d.get("price_now"),
        live_fn=lambda d: _prices_live(d) and d.get("price_now") is not None,
    ),
    NovoltSnapshotSensorDescription(
        key="price_injection",
        translation_key="price_injection",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=4,
        value_fn=lambda d: d.get("injection_now"),
        live_fn=lambda d: _prices_live(d) and d.get("injection_now") is not None,
    ),
)

_PRICE_FIELD = {"price_current": "retail", "price_injection": "injection"}


def _price_curve_attributes(
    insights: dict[str, Any] | None, field: str
) -> dict[str, Any] | None:
    """Day-ahead curve as chart-ready attributes (ApexCharts-friendly)."""
    if not insights:
        return None
    prices = insights.get("prices") or {}
    points = prices.get("prices") or []
    if not prices.get("prices_live") or not points:
        return None
    today = dt_util.now().date()
    raw_today: list[dict[str, Any]] = []
    raw_tomorrow: list[dict[str, Any]] = []
    for point in points:
        start = dt_util.parse_datetime(point.get("time") or "")
        value = point.get(field)
        if start is None or value is None:
            continue
        slot = {"start": point["time"], "price": value}
        slot_date = dt_util.as_local(start).date()
        if slot_date == today:
            raw_today.append(slot)
        elif slot_date > today:
            raw_tomorrow.append(slot)
    attrs: dict[str, Any] = {
        "raw_today": raw_today,
        "raw_tomorrow": raw_tomorrow,
        "tomorrow_valid": bool(raw_tomorrow),
    }
    if raw_today:
        values = [slot["price"] for slot in raw_today]
        attrs["today_min"] = min(values)
        attrs["today_max"] = max(values)
        attrs["today_mean"] = round(sum(values) / len(values), 5)
    return attrs


class NovoltSnapshotSensor(NovoltEntity, SensorEntity):
    """A sensor whose value comes straight out of the live snapshot."""

    entity_description: NovoltSnapshotSensorDescription

    def __init__(
        self,
        entry: NovoltConfigEntry,
        description: NovoltSnapshotSensorDescription,
    ) -> None:
        super().__init__(entry.runtime_data.snapshot, entry, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.live_fn(self.coordinator.data)

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)


class NovoltPriceSensor(NovoltSnapshotSensor):
    """Current price on the fast loop, day-ahead curve from the insights loop."""

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return _price_curve_attributes(
            self._entry.runtime_data.insights.data,
            _PRICE_FIELD[self.entity_description.key],
        )


# ── per-source PV sensors (one entity per inverter) ─────────────────────────


class NovoltPvSourceSensor(NovoltEntity, SensorEntity):
    """One inverter's own PV power, beside the site total.

    A source that drops out of ``pv_sources`` takes this entity to
    ``unavailable`` with it (see :func:`derive.find_pv_source`).
    """

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_translation_key = "pv_source_power"

    def __init__(self, entry: NovoltConfigEntry, source: str) -> None:
        super().__init__(entry.runtime_data.snapshot, entry, f"pv_source_{source}")
        self._source = source
        self._attr_translation_placeholders = {"source": source}

    @property
    def available(self) -> bool:
        return (
            super().available
            and _snapshot_live(self.coordinator.data)
            and find_pv_source(self.coordinator.data, self._source) is not None
        )

    @property
    def native_value(self) -> StateType:
        entry = find_pv_source(self.coordinator.data, self._source)
        return None if entry is None else entry.get("power_w")


# ── per-charger sensors (one device per charger) ────────────────────────────


@dataclass(frozen=True, kw_only=True)
class NovoltChargerSensorDescription(SensorEntityDescription):
    """Describes one per-charger sensor fed by ``snapshot.chargers[]``."""

    value_fn: Callable[[dict[str, Any]], StateType]
    # Offline chargers are reported as 0 W by the API. For a measurement that
    # is a fabricated reading, so power/session/limit go unavailable instead;
    # the status sensor is the one entity that must still say "offline".
    offline_ok: bool = False


CHARGER_SENSORS: tuple[NovoltChargerSensorDescription, ...] = (
    NovoltChargerSensorDescription(
        key="power",
        translation_key="charger_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda c: c.get("power_w"),
    ),
    NovoltChargerSensorDescription(
        key="session_energy",
        translation_key="charger_session_energy",
        device_class=SensorDeviceClass.ENERGY,
        # A session counter resets to 0 when the next car plugs in, which is
        # exactly the reset TOTAL_INCREASING is meant to absorb.
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda c: c.get("session_kwh"),
    ),
    NovoltChargerSensorDescription(
        key="current_limit",
        translation_key="charger_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda c: c.get("limit_a"),
    ),
    NovoltChargerSensorDescription(
        key="status",
        translation_key="charger_status",
        device_class=SensorDeviceClass.ENUM,
        options=CHARGER_STATUSES,
        value_fn=charger_status,
        offline_ok=True,
    ),
)


class NovoltChargerSensor(NovoltEntity, SensorEntity):
    """A sensor for one charger of the site."""

    entity_description: NovoltChargerSensorDescription

    def __init__(
        self,
        entry: NovoltConfigEntry,
        charger: dict[str, Any],
        description: NovoltChargerSensorDescription,
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
    def _data(self) -> dict[str, Any] | None:
        charger = find_charger(self.coordinator.data, self._charger_id)
        if charger is None:
            return None
        if not self.entity_description.offline_ok and charger.get("status") == "offline":
            return None
        return charger

    @property
    def available(self) -> bool:
        if not super().available or not _snapshot_live(self.coordinator.data):
            return False
        charger = self._data
        return charger is not None and self.entity_description.value_fn(charger) is not None

    @property
    def native_value(self) -> StateType:
        charger = self._data
        return None if charger is None else self.entity_description.value_fn(charger)


# ── energy sensors (client-side integrated counters) ────────────────────────


@dataclass(frozen=True, kw_only=True)
class NovoltEnergySensorDescription(SensorEntityDescription):
    """Describes one cumulative energy counter integrated from live power."""

    source_fn: Callable[[dict[str, Any]], float | None]
    exists_fn: Callable[[dict[str, Any]], bool] = lambda caps: True


def _non_negative(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return max(float(value), 0.0)


ENERGY_SENSORS: tuple[NovoltEnergySensorDescription, ...] = (
    NovoltEnergySensorDescription(
        key="pv_energy_total",
        translation_key="pv_energy_total",
        source_fn=lambda d: _non_negative(d.get("pv_w")),
        exists_fn=_has_solar,
    ),
    NovoltEnergySensorDescription(
        key="grid_import_energy_total",
        translation_key="grid_import_energy_total",
        source_fn=lambda d: _non_negative(d.get("grid_import_w")),
    ),
    NovoltEnergySensorDescription(
        key="grid_export_energy_total",
        translation_key="grid_export_energy_total",
        source_fn=lambda d: _non_negative(d.get("grid_export_w")),
    ),
    NovoltEnergySensorDescription(
        key="battery_charge_energy_total",
        translation_key="battery_charge_energy_total",
        source_fn=lambda d: _non_negative(d.get("battery_w")),
        exists_fn=_has_battery,
    ),
    NovoltEnergySensorDescription(
        key="battery_discharge_energy_total",
        translation_key="battery_discharge_energy_total",
        source_fn=lambda d: (
            _non_negative(-d["battery_w"])
            if isinstance(d.get("battery_w"), (int, float))
            else None
        ),
        exists_fn=_has_battery,
    ),
)


class NovoltEnergySensor(NovoltEntity, RestoreSensor):
    """Cumulative kWh counter, trapezoid-integrated from the live snapshot.

    The counter only advances between two *fresh* samples less than
    ``ENERGY_MAX_GAP_S`` apart — an offline gap is skipped, never bridged, so
    the counter contains only energy that was actually observed flowing.
    Restored across restarts; integration restarts from the first new sample.
    """

    entity_description: NovoltEnergySensorDescription
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        entry: NovoltConfigEntry,
        description: NovoltEnergySensorDescription,
    ) -> None:
        super().__init__(entry.runtime_data.snapshot, entry, description.key)
        self.entity_description = description
        self._total_kwh: float | None = None
        self._last_sample: tuple[float, float] | None = None  # (unix ts, watts)

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._total_kwh = float(last.native_value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                self._total_kwh = 0.0
        else:
            self._total_kwh = 0.0
        await super().async_added_to_hass()
        self._accumulate()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._accumulate()
        super()._handle_coordinator_update()

    @callback
    def _accumulate(self) -> None:
        data = self.coordinator.data
        if not self.coordinator.last_update_success or not data or not _snapshot_live(data):
            # Stale/no telemetry: pause and drop the anchor sample, so the
            # offline window is never integrated as if power kept flowing.
            self._last_sample = None
            return
        watts = self.entity_description.source_fn(data)
        if watts is None:
            self._last_sample = None
            return
        now = time.time()
        if self._last_sample is not None:
            elapsed = now - self._last_sample[0]
            if 0 < elapsed <= ENERGY_MAX_GAP_S and self._total_kwh is not None:
                mean_w = (self._last_sample[1] + watts) / 2
                self._total_kwh += mean_w * elapsed / 3_600_000
        self._last_sample = (now, watts)

    @property
    def available(self) -> bool:
        # The counter itself stays valid while the site is briefly stale — it
        # simply pauses. Unavailable only before the first restore/sample.
        return self._total_kwh is not None

    @property
    def native_value(self) -> StateType:
        if self._total_kwh is None:
            return None
        return round(self._total_kwh, 3)


# ── insights sensors (slow loop: today + plan) ──────────────────────────────


@dataclass(frozen=True, kw_only=True)
class NovoltInsightsSensorDescription(SensorEntityDescription):
    """Describes one sensor fed by the combined prices/plan/today payload."""

    value_fn: Callable[[dict[str, Any]], StateType]
    live_fn: Callable[[dict[str, Any]], bool] = _always
    exists_fn: Callable[[dict[str, Any]], bool] = lambda caps: True
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None


def _today_live(data: dict[str, Any]) -> bool:
    return bool((data.get("today") or {}).get("live"))


def _plan_live(data: dict[str, Any]) -> bool:
    return bool((data.get("plan") or {}).get("live"))


def _plan_prices_live(data: dict[str, Any]) -> bool:
    return bool((data.get("plan") or {}).get("prices_live"))


def _today_value(field: str) -> Callable[[dict[str, Any]], StateType]:
    return lambda data: (data.get("today") or {}).get(field)


def _plan_schedule_attributes(data: dict[str, Any]) -> dict[str, Any] | None:
    plan = data.get("plan") or {}
    forecast = plan.get("forecast") or {}
    return {
        "method": forecast.get("method"),
        "generated_at": forecast.get("generated_at"),
        "schedule": plan.get("schedule", []),
    }


def _battery_plan_power(data: dict[str, Any]) -> StateType:
    forecast = (data.get("plan") or {}).get("forecast") or {}
    value = forecast.get("p_batt_forecast_w")
    if not isinstance(value, (int, float)):
        return None
    # Solver convention is charge-negative; flip to the canonical charge-
    # positive sign every other battery entity uses.
    return round(-float(value))


def _slot(field: str, digits: int = 0) -> Callable[[dict[str, Any]], StateType]:
    """Bind :func:`derive.plan_slot_value` to one schedule field."""
    return lambda data: plan_slot_value(data, field, digits)


def _series(field: str) -> Callable[[dict[str, Any]], dict[str, Any] | None]:
    """Bind :func:`derive.plan_series` to one schedule field."""
    return lambda data: plan_series(data, field)


def _ev_next_cheap_start(data: dict[str, Any]) -> Any:
    schedule = ((data.get("plan") or {}).get("ev") or {}).get("schedule") or []
    now = dt_util.now()
    for slot in schedule:
        if not slot.get("charge"):
            continue
        start = dt_util.parse_datetime(slot.get("date") or "")
        if start is not None and dt_util.as_local(start) >= now:
            return start
    return None


INSIGHTS_SENSORS: tuple[NovoltInsightsSensorDescription, ...] = (
    NovoltInsightsSensorDescription(
        key="today_pv_energy",
        translation_key="today_pv_energy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=_today_value("pv_kwh"),
        live_fn=_today_live,
        exists_fn=_has_solar,
    ),
    NovoltInsightsSensorDescription(
        key="today_grid_import",
        translation_key="today_grid_import",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=_today_value("import_kwh"),
        live_fn=_today_live,
    ),
    NovoltInsightsSensorDescription(
        key="today_grid_export",
        translation_key="today_grid_export",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=_today_value("export_kwh"),
        live_fn=_today_live,
    ),
    NovoltInsightsSensorDescription(
        key="today_battery_charge",
        translation_key="today_battery_charge",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=_today_value("batt_charge_kwh"),
        live_fn=_today_live,
        exists_fn=_has_battery,
    ),
    NovoltInsightsSensorDescription(
        key="today_battery_discharge",
        translation_key="today_battery_discharge",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=_today_value("batt_discharge_kwh"),
        live_fn=_today_live,
        exists_fn=_has_battery,
    ),
    NovoltInsightsSensorDescription(
        key="self_sufficiency",
        translation_key="self_sufficiency",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_today_value("self_sufficiency_pct"),
        live_fn=_today_live,
    ),
    NovoltInsightsSensorDescription(
        key="battery_command",
        translation_key="battery_command",
        device_class=SensorDeviceClass.ENUM,
        options=BATTERY_COMMANDS,
        value_fn=lambda d: ((d.get("plan") or {}).get("battery") or {}).get("command"),
        live_fn=_plan_live,
        exists_fn=_has_battery,
        attributes_fn=lambda d: {
            "reason": ((d.get("plan") or {}).get("battery") or {}).get("reason"),
            "power_w": ((d.get("plan") or {}).get("battery") or {}).get("power_w"),
        },
    ),
    NovoltInsightsSensorDescription(
        key="battery_plan_power",
        translation_key="battery_plan_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_battery_plan_power,
        live_fn=lambda d: _plan_live(d)
        and ((d.get("plan") or {}).get("forecast") or {}).get("method") != "none",
        exists_fn=_has_battery,
        attributes_fn=_plan_schedule_attributes,
    ),
    NovoltInsightsSensorDescription(
        key="ev_next_cheap_start",
        translation_key="ev_next_cheap_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_ev_next_cheap_start,
        live_fn=_plan_prices_live,
        exists_fn=_has_ev,
    ),
    # ── euros: what the site saved and what it actually cost ──────────────
    # No state_class: these are trailing-24 h rolling figures, and letting the
    # statistics engine sum them would invent a total nobody measured.
    NovoltInsightsSensorDescription(
        key="today_saved",
        translation_key="today_saved",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EUR,
        suggested_display_precision=2,
        value_fn=_today_value("saved_eur"),
        # null means no defensible figure (no prices for this contract, or no
        # flows) — unavailable, never a fabricated € 0.
        live_fn=lambda d: _today_live(d) and (d.get("today") or {}).get("saved_eur") is not None,
    ),
    NovoltInsightsSensorDescription(
        key="today_cost",
        translation_key="today_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EUR,
        suggested_display_precision=2,
        value_fn=_today_value("cost_eur"),
        live_fn=lambda d: _today_live(d) and (d.get("today") or {}).get("cost_eur") is not None,
    ),
    # ── the rest of the forecast the planner already computed ─────────────
    NovoltInsightsSensorDescription(
        key="pv_forecast_power",
        translation_key="pv_forecast_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_slot("pv_w"),
        live_fn=forecast_live,
        exists_fn=_has_solar,
        attributes_fn=_series("pv_w"),
    ),
    NovoltInsightsSensorDescription(
        key="load_forecast_power",
        translation_key="load_forecast_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_slot("load_w"),
        live_fn=forecast_live,
        attributes_fn=_series("load_w"),
    ),
    NovoltInsightsSensorDescription(
        key="grid_forecast_power",
        translation_key="grid_forecast_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        # Same canonical sign as the live grid sensor: import positive.
        value_fn=_slot("grid_w"),
        live_fn=forecast_live,
        attributes_fn=_series("grid_w"),
    ),
    NovoltInsightsSensorDescription(
        key="battery_soc_forecast",
        translation_key="battery_soc_forecast",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        # soc_pct is null on a forecast-only plan (no battery to track), which
        # the value/live pair turns into unavailable rather than 0 %.
        value_fn=_slot("soc_pct", digits=1),
        live_fn=lambda d: forecast_live(d)
        and _slot("soc_pct", digits=1)(d) is not None,
        exists_fn=_has_battery,
        attributes_fn=_series("soc_pct"),
    ),
    # ── EV charge quota ("5 uur = 5 uur") ─────────────────────────────────
    NovoltInsightsSensorDescription(
        key="ev_hours_done",
        translation_key="ev_hours_done",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda d: ev_hours(d, "done_hours"),
        live_fn=_plan_live,
        exists_fn=_has_ev,
        attributes_fn=ev_hours_attributes,
    ),
    NovoltInsightsSensorDescription(
        key="ev_hours_remaining",
        translation_key="ev_hours_remaining",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda d: ev_hours(d, "remaining_hours"),
        live_fn=_plan_live,
        exists_fn=_has_ev,
        attributes_fn=ev_hours_attributes,
    ),
    # ── EV charge quota in kilometers ─────────────────────────────────────
    # The same two numbers in the unit the customer stated the job in. Absent
    # (unavailable) on a site that charges by the hour: see derive.ev_km.
    NovoltInsightsSensorDescription(
        key="ev_km_done",
        translation_key="ev_km_done",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda d: ev_km(d, "done_km"),
        live_fn=_plan_live,
        exists_fn=_has_ev,
        attributes_fn=ev_hours_attributes,
    ),
    NovoltInsightsSensorDescription(
        key="ev_km_remaining",
        translation_key="ev_km_remaining",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda d: ev_km(d, "remaining_km"),
        live_fn=_plan_live,
        exists_fn=_has_ev,
        attributes_fn=ev_hours_attributes,
    ),
    # ── the plan's own grid peak, with the measured reality beside it ─────
    NovoltInsightsSensorDescription(
        key="plan_grid_peak",
        translation_key="plan_grid_peak",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: ((d.get("plan") or {}).get("peak_shaving") or {}).get("planned_peak_w"),
        live_fn=lambda d: forecast_live(d)
        and ((d.get("plan") or {}).get("peak_shaving") or {}).get("planned_peak_w") is not None,
        attributes_fn=peak_shaving_attributes,
    ),
)


class NovoltInsightsSensor(NovoltEntity, SensorEntity):
    """A sensor fed by the slow prices/plan/today loop."""

    entity_description: NovoltInsightsSensorDescription

    def __init__(
        self,
        entry: NovoltConfigEntry,
        description: NovoltInsightsSensorDescription,
    ) -> None:
        super().__init__(entry.runtime_data.insights, entry, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.live_fn(self.coordinator.data)

    @property
    def native_value(self) -> StateType:
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
    """Set up Novolt sensors, gated by the site's resolved capabilities."""
    snapshot = entry.runtime_data.snapshot.data or {}
    caps = snapshot.get("capabilities") or {}
    entities: list[SensorEntity] = [
        NovoltSnapshotSensor(entry, description)
        for description in SNAPSHOT_SENSORS
        if description.exists_fn(caps)
    ]
    entities.extend(NovoltPriceSensor(entry, description) for description in PRICE_SENSORS)
    # Per-charger and per-inverter entities are discovered from the first
    # snapshot. Registered chargers are always in that list (offline ones
    # included), so only an unregistered charger or a brand-new inverter needs
    # a reload of the integration before it gets its own entities.
    if _has_ev(caps):
        for charger in snapshot.get("chargers") or []:
            if not charger.get("id"):
                continue
            entities.extend(
                NovoltChargerSensor(entry, charger, description)
                for description in CHARGER_SENSORS
            )
    # Only worth splitting out when there is more than one inverter: on a
    # single-source site the per-source entity is just pv_power again.
    pv_sources = [s["source"] for s in snapshot.get("pv_sources") or [] if s.get("source")]
    if _has_solar(caps) and len(pv_sources) > 1:
        entities.extend(NovoltPvSourceSensor(entry, source) for source in pv_sources)
    entities.extend(
        NovoltEnergySensor(entry, description)
        for description in ENERGY_SENSORS
        if description.exists_fn(caps)
    )
    entities.extend(
        NovoltInsightsSensor(entry, description)
        for description in INSIGHTS_SENSORS
        if description.exists_fn(caps)
    )
    async_add_entities(entities)
