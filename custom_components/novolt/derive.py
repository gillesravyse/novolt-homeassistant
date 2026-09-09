"""Pure payload logic behind the entities: dicts in, values out.

Deliberately free of Home Assistant imports, for the same reason ``api.py``
is: everything in here is a claim about what the ``/v1`` payload *means*, and
that is exactly the part worth testing without a Home Assistant install.

Every function returns ``None``/empty rather than a substitute number when the
payload has nothing real to say. The entity layer turns that into
``unavailable``; it never turns it into a zero.
"""

from __future__ import annotations

from typing import Any

# Canonical charger statuses (novolt_core.capabilities.ChargerStatus) plus the
# API's "offline" for a registered charger without a fresh sample.
CHARGER_STATUSES = [
    "offline",
    "disconnected",
    "awaiting_start",
    "ready_to_charge",
    "charging",
    "completed",
    "error",
    "unknown",
]

# Methods that mean a real plan was solved. "none" (nothing to plan) and
# "interim" (the price-free heuristic) come with an empty schedule.
FORECAST_METHODS = ("lp", "forecast")


# ── snapshot ────────────────────────────────────────────────────────────────


def house_no_ev(data: dict[str, Any]) -> float | None:
    """House load with the EV draw taken out; ``None`` when either is missing."""
    house = data.get("house_load_w")
    ev = data.get("ev_w")
    if not isinstance(house, (int, float)) or not isinstance(ev, (int, float)):
        return None
    return round(max(float(house) - float(ev), 0.0))


def find_charger(data: dict[str, Any], charger_id: str) -> dict[str, Any] | None:
    """The snapshot entry for one charger, or ``None`` when it is not reported."""
    for charger in data.get("chargers") or []:
        if charger.get("id") == charger_id:
            return charger
    return None


def charger_status(charger: dict[str, Any]) -> str:
    """The charger's status, normalised onto the declared enum options.

    A status we don't know yet becomes ``unknown`` instead of breaking the
    entity: a new firmware string must not take the charger off the dashboard.
    """
    status = charger.get("status")
    return status if status in CHARGER_STATUSES else "unknown"


def find_pv_source(data: dict[str, Any], source: str) -> dict[str, Any] | None:
    """One inverter's entry in the PV split, or ``None`` when it dropped out.

    A source that stops vouching for its readings (a frozen SolaxCloud feed)
    disappears from the list, which is what makes the freeze visible instead
    of it silently shrinking the site total.
    """
    for entry in data.get("pv_sources") or []:
        if entry.get("source") == source:
            return entry
    return None


# ── plan / forecast ─────────────────────────────────────────────────────────


def forecast_live(data: dict[str, Any]) -> bool:
    """Whether a real forecast exists: a plan with an actual schedule behind it."""
    plan = data.get("plan") or {}
    if not plan.get("live") or not plan.get("schedule"):
        return False
    return (plan.get("forecast") or {}).get("method") in FORECAST_METHODS


def plan_slot_value(data: dict[str, Any], field: str, digits: int = 0) -> float | None:
    """The current slot's forecast value; the plan's first slot is now."""
    slots = (data.get("plan") or {}).get("schedule") or []
    if not slots:
        return None
    raw = slots[0].get(field)
    if not isinstance(raw, (int, float)):
        return None
    return round(float(raw), digits) if digits else round(float(raw))


def plan_series(data: dict[str, Any], field: str) -> dict[str, Any] | None:
    """The whole 24 h series for one field, chart-ready (ApexCharts-friendly)."""
    plan = data.get("plan") or {}
    series = [
        {"start": slot["time"], "value": slot[field]}
        for slot in plan.get("schedule") or []
        if slot.get("time") and isinstance(slot.get(field), (int, float))
    ]
    if not series:
        return None
    forecast = plan.get("forecast") or {}
    return {
        "forecast": series,
        "method": forecast.get("method"),
        "generated_at": forecast.get("generated_at"),
    }


def peak_shaving_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """The plan's peak beside the measured reality: both, or neither, are honest."""
    peak = (data.get("plan") or {}).get("peak_shaving") or {}
    return {
        "limit_w": peak.get("limit_w"),
        "measured_peak_w": peak.get("measured_peak_w"),
        "within_limit": peak.get("within_limit"),
        "feasible": peak.get("feasible"),
        "p95_grid_need_w": peak.get("p95_grid_need_w"),
        "history_hours": peak.get("history_hours"),
        "history_hours_required": peak.get("history_hours_required"),
    }


# ── EV charge quota ─────────────────────────────────────────────────────────


def ev_hours(data: dict[str, Any], field: str) -> int:
    """Charge hours across both layers: the daily default and every request.

    The default quota only counts while it is actually active. Once every
    charger is covered by its own request the default does not apply, and
    adding its untouched hours would inflate the total.
    """
    ev = (data.get("plan") or {}).get("ev") or {}
    default = ev.get("default") or {}
    total = float(default.get(field, 0)) if default.get("active") else 0.0
    for request in ev.get("requests") or []:
        total += float(request.get(field, 0))
    return round(total)


def ev_km(data: dict[str, Any], field: str) -> int | None:
    """Charge kilometers across both layers, or ``None`` when nothing uses them.

    The distance twin of :func:`ev_hours`, and it returns ``None`` rather than 0
    on a site that states its charging jobs in hours: those jobs carry no
    kilometers at all, and a zero here would read as "nothing left to charge"
    instead of "this site does not charge in kilometers". Home Assistant renders
    that as unavailable, which is the honest state.

    Same activity rule as the hours: a daily quota only counts while it is
    actually driving a charger.
    """
    ev = (data.get("plan") or {}).get("ev") or {}
    entries = [e for e in ev.get("defaults") or [] if e.get("active")]
    entries += list(ev.get("requests") or [])
    total = 0.0
    seen = False
    for entry in entries:
        if entry.get("goal") != "km":
            continue
        value = entry.get(field)
        if value is None:
            continue
        seen = True
        total += float(value)
    return round(total) if seen else None


def ev_hours_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """The quota's breakdown, without the hour-by-hour schedules.

    Those live on the EV cheap-hour binary sensor; repeating them here would
    put the same fat payload in the state machine several times over.

    ``default`` is the site-level roll-up of the daily schedule; ``defaults``
    breaks it down per charger, since each one can carry its own cheap-hour
    quota and ready-by hour. Older platforms send no ``defaults`` at all — the
    attribute is then simply absent rather than a fabricated single entry.
    """
    ev = (data.get("plan") or {}).get("ev") or {}
    attributes: dict[str, Any] = {
        "default": ev.get("default") or {},
        "requests": [
            {key: value for key, value in request.items() if key != "schedule"}
            for request in ev.get("requests") or []
        ],
    }
    defaults = ev.get("defaults")
    if isinstance(defaults, list):
        attributes["defaults"] = [
            {key: value for key, value in entry.items() if key != "schedule"}
            for entry in defaults
        ]
    return attributes
