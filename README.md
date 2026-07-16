<p align="center">
  <img src="custom_components/novolt/brand/logo@2x.png" alt="Novolt" width="340">
</p>

# Novolt for Home Assistant

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gillesravyse&repository=novolt-homeassistant&category=integration)

Bring your [Novolt](https://novolt.be) site into Home Assistant: live power flows, battery state, dynamic electricity prices, the dispatch plan and Energy Dashboard-ready energy counters — all through Novolt's read-only cloud API.

## Features

- **Live power flows** — PV, grid (net / import / export), house load, battery power & state of charge, EV charging power (30 s polling by default).
- **Energy Dashboard ready** — cumulative kWh counters for grid import/export, PV production and battery charge/discharge, integrated from the live measurements and restored across restarts.
- **Dynamic prices** — the current retail and injection price for *your* tariff, with the full day-ahead curve as attributes (works with ApexCharts cards).
- **Dispatch plan** — the battery command Novolt is running (idle / force charge / force discharge), the planned battery power with the 24 h schedule as attributes, and the cheap EV-charging hours.
- **Honest data** — when telemetry or prices are stale or missing, entities become `unavailable`. You will never see a fabricated zero.

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

## Energy Dashboard

Use these entities in **Settings → Dashboards → Energy**:

| Energy Dashboard slot | Entity |
| --- | --- |
| Grid consumption | `sensor.novolt_grid_import_energy` |
| Return to grid | `sensor.novolt_grid_export_energy` |
| Solar production | `sensor.novolt_pv_energy` |
| Battery in | `sensor.novolt_battery_charge_energy` |
| Battery out | `sensor.novolt_battery_discharge_energy` |

These counters integrate the live power readings client-side (trapezoid rule) and only advance while fresh telemetry is flowing — offline gaps are skipped, never bridged.

## Entities

| Entity | Description |
| --- | --- |
| PV / Grid / House / Battery / EV power | Live powers in W (grid & battery also as net values: import/charge positive) |
| Battery | State of charge (%) |
| Current price / injection price | €/kWh for your tariff, day-ahead curve in `raw_today` / `raw_tomorrow` attributes |
| Battery command | What the optimizer is doing now (`idle`, `force_charge`, `force_discharge`) with the reason as attribute |
| Planned battery power | The optimizer's target for the current slot, 24 h schedule as attribute |
| EV cheap hour / Next cheap EV hour | Whether now is a selected cheap charging hour, and when the next one starts |
| … last 24h | Trailing-24 h energy aggregates and self-sufficiency as reported by Novolt |
| Live data / Live prices | Diagnostic flags: is fresh telemetry / a real price curve available? |

## Notes

- The integration is **read-only** by construction: Novolt API keys can only read your own site's data. Control actions stay in the Novolt platform.
- Requires Home Assistant 2024.8 or newer.
- Issues and feature requests: [GitHub issues](https://github.com/gillesravyse/novolt-homeassistant/issues).
