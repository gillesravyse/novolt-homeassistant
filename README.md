<p align="center">
  <img src="custom_components/novolt/brand/logo@2x.png" alt="Novolt" width="340">
</p>

# Novolt for Home Assistant

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gillesravyse&repository=novolt-homeassistant&category=integration)

Bring your [Novolt](https://novolt.be) site into Home Assistant: live power flows, battery state, dynamic electricity prices, the dispatch plan and Energy Dashboard-ready energy counters, all through Novolt's read-only cloud API.

## Features

- **Live power flows**: PV, grid (net / import / export), house load (with and without the cars), battery power & state of charge, EV charging power (30 s polling by default).
- **Energy Dashboard ready**: cumulative kWh counters for grid import/export, PV production and battery charge/discharge, integrated from the live measurements and restored across restarts.
- **Dynamic prices**: the current retail and injection price for *your* tariff, with the full day-ahead curve as attributes (works with ApexCharts cards).
- **What it saved you**: the savings and the real cost over the trailing 24 h, in euros, straight from Novolt's savings model.
- **Every charger separately**: each charging station becomes its own device with power, session energy, current limit, status, online and charging entities.
- **The full 24 h forecast**: not just the battery plan but the sun, house-load, grid and state-of-charge trajectories behind it, each with its own chart-ready series.
- **Honest data**: when telemetry or prices are stale or missing, entities become `unavailable`. You will never see a fabricated zero.

Entities adapt to your site: a home without a battery gets no battery entities, PV-only sites get no EV entities, and so on.

## Installation

### HACS (recommended)

1. In HACS, choose **⋮ → Custom repositories**.
2. Add `https://github.com/gillesravyse/novolt-homeassistant` as an **Integration**.
3. Install **Novolt** and restart Home Assistant.

### Manual

Copy `custom_components/novolt/` into your Home Assistant `config/custom_components/` directory and restart.

## Configuration

1. In the Novolt app ([app.novolt.be](https://app.novolt.be)), go to **Settings → API** and create an API key (`novolt_sk_…`).
2. In Home Assistant: **Settings → Devices & services → Add integration → Novolt**.
3. Paste the key. Done.

Polling intervals are tunable via the integration's **Configure** button (defaults: 30 s for the live snapshot, 5 min for prices/plan/aggregates).

> [!NOTE]
> Home Assistant generates entity IDs from the entity names in **your interface language** when the integration is first added. On a Dutch install the price sensor is `sensor.novolt_huidige_prijs`, not `sensor.novolt_current_price`. All examples below use the English IDs; find your actual IDs under **Settings → Devices & services → Novolt → entities** and adjust where needed.

## Energy Dashboard

Use these entities in **Settings → Dashboards → Energy**:

| Energy Dashboard slot | Entity |
| --- | --- |
| Grid consumption | `sensor.novolt_grid_import_energy` |
| Return to grid | `sensor.novolt_grid_export_energy` |
| Solar production | `sensor.novolt_pv_energy` |
| Battery in | `sensor.novolt_battery_charge_energy` |
| Battery out | `sensor.novolt_battery_discharge_energy` |

These counters integrate the live power readings client-side (trapezoid rule) and only advance while fresh telemetry is flowing. Offline gaps are skipped, never bridged.

## Bundled dashboard cards

The integration ships five custom Lovelace cards, styled identically to the Novolt app. No extra install and no resource configuration: after adding the integration they simply appear in the card picker (**Add card → search "Novolt"**). Entities are auto-discovered, so an empty config `{}` works in any language:

| Card | What it shows |
| --- | --- |
| `custom:novolt-power-flow-card` | The live energy flow between sun, grid, home, battery and EV chargers, with animated flows and the SOC ring |
| `custom:novolt-battery-card` | State-of-charge ring plus today's charged and discharged energy |
| `custom:novolt-stats-card` | Stat tiles: current price (with the next cheap hour), sun today, self-sufficiency and injection price |
| `custom:novolt-price-card` | Day-ahead price columns with the selected cheap charging hours and a now-marker |
| `custom:novolt-forecast-card` | The 24 h plan: sun and consumption forecast, battery charge/discharge plan and SOC trajectory |

Every card accepts optional overrides when auto-discovery is not what you want:

```yaml
type: custom:novolt-power-flow-card
reference_w: 3000
entities:
  pv_power: sensor.novolt_pv_vermogen
```

## Dashboard ideas

### Day-ahead price chart

The price sensors carry the full day-ahead curve in their `raw_today` / `raw_tomorrow` attributes, ready for [ApexCharts card](https://github.com/RomRider/apexcharts-card):

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Electricity price (€/kWh)
graph_span: 24h
span:
  start: day
now:
  show: true
  label: now
series:
  - entity: sensor.novolt_current_price
    name: Import
    type: column
    data_generator: |
      return entity.attributes.raw_today.map((p) => {
        return [new Date(p.start).getTime(), p.price];
      });
  - entity: sensor.novolt_current_injection_price
    name: Injection
    type: line
    curve: stepline
    data_generator: |
      return entity.attributes.raw_today.map((p) => {
        return [new Date(p.start).getTime(), p.price];
      });
```

### Live site overview

```yaml
type: entities
title: Novolt
entities:
  - entity: sensor.novolt_pv_power
  - entity: sensor.novolt_house_power
  - entity: sensor.novolt_grid_power
  - entity: sensor.novolt_battery_power
  - entity: sensor.novolt_battery
  - entity: sensor.novolt_ev_power
  - entity: sensor.novolt_battery_command
  - entity: binary_sensor.novolt_ev_cheap_hour
```

### Automation: run the dishwasher in cheap hours

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.novolt_current_price
    below: 0.10
conditions:
  - condition: state
    entity_id: binary_sensor.novolt_live_data
    state: "on"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.dishwasher
```

## Entities

### On the site device

| Entity | Description |
| --- | --- |
| PV / Grid / House / Battery / EV power | Live powers in W (grid & battery also as net values: import/charge positive) |
| House power excl. EV | The same house load with the cars taken out: your baseline consumption |
| PV power `<source>` | One entity per inverter when your site has more than one, so a frozen cloud feed shows up as `unavailable` instead of quietly shrinking the total |
| Battery | State of charge (%) |
| Current price / injection price | €/kWh for your tariff, day-ahead curve in `raw_today` / `raw_tomorrow` attributes |
| Savings / Cost today | What Novolt saved you and what the electricity actually cost since midnight, in € |
| Battery command | What the optimizer is doing now (`idle`, `force_charge`, `force_discharge`) with the reason as attribute |
| Planned battery power | The optimizer's target for the current slot, 24 h schedule as attribute |
| Forecast PV / house / grid power, Forecast battery | The rest of the 24 h plan: the current slot as state, the whole series in the `forecast` attribute |
| Planned grid peak | The peak the plan draws, with your limit and the *measured* peak beside it in the attributes |
| EV cheap hour / Next cheap EV hour | Whether now is a selected cheap charging hour, and when the next one starts |
| EV charge hours done / remaining | Progress on the charge quota, across both the daily default and any explicit charge requests |
| EV charging | Whether any charger is actually delivering power right now |
| … today | Energy aggregates and self-sufficiency since local midnight, as reported by Novolt |
| Live data / Live prices | Diagnostic flags: is fresh telemetry / a real price curve available? |

### On each charger device

Every charging station Novolt knows about becomes its own device under the site, named as in the Novolt app.

| Entity | Description |
| --- | --- |
| Power | What this charger is drawing (W) |
| Session energy | Energy delivered in the running session (kWh); resets when the next car plugs in |
| Current limit | The dynamic charging limit the charger is applying (A) |
| Status | `charging`, `ready_to_charge`, `disconnected`, `offline`, … |
| Online / Charging | Is the charger reporting, and is it actually charging? |

An offline charger reports its status as `offline`; its power, session and limit entities go `unavailable` rather than claiming a measured 0.

> [!NOTE]
> Chargers and inverters are discovered when the integration loads. After adding one in the Novolt app, reload the integration (**⋮ → Reload**) to get its entities.

## Notes

- The integration is **read-only** by construction: Novolt API keys can only read your own site's data. Control actions stay in the Novolt platform.
- Requires Home Assistant 2024.8 or newer.
- Issues and feature requests: [GitHub issues](https://github.com/gillesravyse/novolt-homeassistant/issues).
