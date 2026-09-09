"""Tests for the payload logic behind the entities (no Home Assistant involved).

The recurring assertion is the honesty rule: when the payload has nothing real
to say, these helpers return ``None``/``False`` so the entity can go
``unavailable``. A zero here would become a measurement on someone's dashboard.
"""

from novolt_derive import (
    CHARGER_STATUSES,
    charger_status,
    ev_hours,
    ev_km,
    ev_hours_attributes,
    find_charger,
    find_pv_source,
    forecast_live,
    house_no_ev,
    peak_shaving_attributes,
    plan_series,
    plan_slot_value,
)

import pytest

SNAPSHOT = {
    "live": True,
    "house_load_w": 9200,
    "ev_w": 7400,
    "pv_sources": [
        {"source": "solax", "power_w": 1200},
        {"source": "solis", "power_w": 3000},
    ],
    "chargers": [
        {
            "id": "LEFT",
            "name": "Lader links",
            "vendor": "easee",
            "power_w": 7400,
            "status": "charging",
            "session_kwh": 12.34,
            "limit_a": 16.0,
        },
        {
            "id": "RIGHT",
            "name": "Lader rechts",
            "vendor": "easee",
            "power_w": 0,
            "status": "offline",
            "session_kwh": None,
            "limit_a": None,
        },
    ],
}

PLAN = {
    "plan": {
        "live": True,
        "forecast": {"method": "lp", "generated_at": "2026-07-23T10:00:00+02:00"},
        "schedule": [
            {
                "time": "2026-07-23T10:00:00+02:00",
                "pv_w": 4100.4,
                "load_w": 900.0,
                "grid_w": -700.0,
                "soc_pct": 62.4,
            },
            {
                "time": "2026-07-23T11:00:00+02:00",
                "pv_w": 5000.0,
                "load_w": 800.0,
                "grid_w": -1700.0,
                "soc_pct": 70.0,
            },
        ],
        "ev": {
            "default": {
                "active": True,
                "cheap_hours": 5,
                "done_hours": 1,
                "remaining_hours": 4,
            },
            "requests": [
                {
                    "charger_id": "LEFT",
                    "hours": 6,
                    "done_hours": 2,
                    "remaining_hours": 4,
                    "schedule": [{"date": "2026-07-23T23:00:00+02:00", "charge": True}],
                }
            ],
        },
        "peak_shaving": {
            "limit_w": 6000.0,
            "planned_peak_w": 3400.0,
            "measured_peak_w": 8100.0,
            "within_limit": True,
            "feasible": False,
            "p95_grid_need_w": 7200.0,
            "history_hours": 336,
            "history_hours_required": 168,
        },
    }
}


# ── house load without the cars ─────────────────────────────────────────────


def test_house_no_ev_subtracts_the_chargers():
    assert house_no_ev(SNAPSHOT) == 1800


def test_house_no_ev_never_goes_negative():
    # Sampling skew can put the EV draw above the house total for one tick.
    assert house_no_ev({"house_load_w": 100, "ev_w": 500}) == 0


@pytest.mark.parametrize(
    "data",
    [{"house_load_w": 900}, {"ev_w": 500}, {"house_load_w": None, "ev_w": 500}, {}],
)
def test_house_no_ev_needs_both_halves(data):
    assert house_no_ev(data) is None


# ── chargers ────────────────────────────────────────────────────────────────


def test_find_charger_by_id():
    assert find_charger(SNAPSHOT, "RIGHT")["name"] == "Lader rechts"


@pytest.mark.parametrize("data", [SNAPSHOT, {}, {"chargers": None}])
def test_find_charger_missing_is_none(data):
    assert find_charger(data, "NOPE") is None


def test_charger_status_passes_known_values_through():
    assert charger_status({"status": "charging"}) == "charging"
    assert charger_status({"status": "offline"}) == "offline"


@pytest.mark.parametrize("raw", ["some_new_firmware_state", None, 42, ""])
def test_charger_status_normalises_the_unexpected(raw):
    # An unknown status must not break the enum entity: the charger stays on
    # the dashboard, honestly labelled as unknown.
    assert charger_status({"status": raw}) == "unknown"
    assert charger_status({"status": raw}) in CHARGER_STATUSES


# ── per-inverter PV ─────────────────────────────────────────────────────────


def test_find_pv_source():
    assert find_pv_source(SNAPSHOT, "solis")["power_w"] == 3000


def test_frozen_feed_drops_out_of_the_split():
    # A SolaxCloud feed that stops vouching for its readings disappears from
    # pv_sources; the entity must go unavailable, not report its last value.
    frozen = {"pv_sources": [{"source": "solis", "power_w": 3000}]}
    assert find_pv_source(frozen, "solax") is None


# ── forecast ────────────────────────────────────────────────────────────────


def test_forecast_live_on_a_solved_plan():
    assert forecast_live(PLAN) is True


@pytest.mark.parametrize("method", ["forecast", "lp"])
def test_forecast_live_accepts_both_real_methods(method):
    data = {"plan": {"live": True, "schedule": [{}], "forecast": {"method": method}}}
    assert forecast_live(data) is True


@pytest.mark.parametrize(
    "plan",
    [
        # Nothing to plan (no battery / no contract rates): empty schedule.
        {"live": True, "schedule": [], "forecast": {"method": "none"}},
        # The price-free heuristic is not a forecast anyone should chart.
        {"live": True, "schedule": [], "forecast": {"method": "interim"}},
        # Stale telemetry.
        {"live": False, "schedule": [{}], "forecast": {"method": "lp"}},
        {},
    ],
)
def test_forecast_not_live_without_a_real_plan(plan):
    assert forecast_live({"plan": plan}) is False


def test_plan_slot_value_reads_the_current_slot():
    # The plan's first slot is now; 4100.4 W is reported as whole watts.
    assert plan_slot_value(PLAN, "pv_w") == 4100
    assert plan_slot_value(PLAN, "load_w") == 900


def test_plan_slot_value_keeps_the_canonical_grid_sign():
    # grid_w is import-positive, same as the live grid sensor: this slot exports.
    assert plan_slot_value(PLAN, "grid_w") == -700


def test_plan_slot_value_honours_digits():
    assert plan_slot_value(PLAN, "soc_pct", digits=1) == 62.4


@pytest.mark.parametrize(
    "data",
    [
        {"plan": {"schedule": []}},
        # A forecast-only plan (no battery) carries soc_pct = null.
        {"plan": {"schedule": [{"time": "t", "soc_pct": None}]}},
        {},
    ],
)
def test_plan_slot_value_missing_is_none(data):
    assert plan_slot_value(data, "soc_pct", digits=1) is None


def test_plan_series_is_chart_ready():
    series = plan_series(PLAN, "pv_w")
    assert series["forecast"] == [
        {"start": "2026-07-23T10:00:00+02:00", "value": 4100.4},
        {"start": "2026-07-23T11:00:00+02:00", "value": 5000.0},
    ]
    assert series["method"] == "lp"
    assert series["generated_at"] == "2026-07-23T10:00:00+02:00"


def test_plan_series_skips_slots_without_a_value():
    data = {
        "plan": {
            "schedule": [
                {"time": "a", "soc_pct": 50.0},
                {"time": "b", "soc_pct": None},
                {"soc_pct": 60.0},
            ]
        }
    }
    assert plan_series(data, "soc_pct")["forecast"] == [{"start": "a", "value": 50.0}]


@pytest.mark.parametrize("data", [{"plan": {"schedule": []}}, {}])
def test_plan_series_empty_is_none(data):
    assert plan_series(data, "pv_w") is None


# ── EV charge quota ─────────────────────────────────────────────────────────


def test_ev_hours_sums_default_and_requests():
    assert ev_hours(PLAN, "done_hours") == 3  # 1 default + 2 request
    assert ev_hours(PLAN, "remaining_hours") == 8  # 4 default + 4 request


def test_ev_hours_ignores_an_inactive_default():
    # Every charger covered by its own request: the default quota does not
    # apply, and counting its untouched hours would inflate the total.
    data = {
        "plan": {
            "ev": {
                "default": {"active": False, "done_hours": 0, "remaining_hours": 5},
                "requests": [{"done_hours": 3, "remaining_hours": 2}],
            }
        }
    }
    assert ev_hours(data, "remaining_hours") == 2
    assert ev_hours(data, "done_hours") == 3


@pytest.mark.parametrize("data", [{"plan": {"ev": {}}}, {"plan": {}}, {}])
def test_ev_hours_without_a_plan_is_zero(data):
    assert ev_hours(data, "done_hours") == 0


# ── the same quota in kilometers ────────────────────────────────────────────


def test_ev_km_sums_both_layers():
    data = {
        "plan": {
            "ev": {
                "defaults": [
                    {"active": True, "goal": "km", "done_km": 20, "remaining_km": 40},
                    # Covered by its own request: an inactive rule charges
                    # nothing, so its kilometers must not be counted.
                    {"active": False, "goal": "km", "done_km": 99, "remaining_km": 99},
                ],
                "requests": [
                    {"goal": "km", "done_km": 50, "remaining_km": 100},
                ],
            }
        }
    }
    assert ev_km(data, "done_km") == 70
    assert ev_km(data, "remaining_km") == 140


def test_ev_km_is_none_on_a_site_that_charges_by_the_hour():
    """Not 0: a zero would read as "nothing left to charge" on a site whose
    jobs simply are not stated in kilometers. HA shows that as unavailable."""
    assert ev_km(PLAN, "remaining_km") is None


@pytest.mark.parametrize("data", [{"plan": {"ev": {}}}, {"plan": {}}, {}])
def test_ev_km_without_a_plan_is_none(data):
    assert ev_km(data, "done_km") is None


def test_ev_hours_attributes_strip_the_schedules():
    attrs = ev_hours_attributes(PLAN)
    assert attrs["default"]["cheap_hours"] == 5
    assert attrs["requests"][0]["charger_id"] == "LEFT"
    # The hour-by-hour schedule lives on the EV cheap-hour binary sensor.
    assert "schedule" not in attrs["requests"][0]


# ── peak shaving ────────────────────────────────────────────────────────────


def test_peak_shaving_reports_plan_and_reality_together():
    attrs = peak_shaving_attributes(PLAN)
    # within_limit describes the schedule; measured_peak_w is the reality
    # check beside it. Showing one without the other would mislead.
    assert attrs["within_limit"] is True
    assert attrs["measured_peak_w"] == 8100.0
    assert attrs["feasible"] is False
    assert attrs["history_hours"] == 336


def test_peak_shaving_without_a_limit_stays_null():
    attrs = peak_shaving_attributes({"plan": {}})
    assert set(attrs) == {
        "limit_w",
        "measured_peak_w",
        "within_limit",
        "feasible",
        "p95_grid_need_w",
        "history_hours",
        "history_hours_required",
    }
    assert all(value is None for value in attrs.values())
