"""Constants for the Novolt integration."""

from __future__ import annotations

DOMAIN = "novolt"

CONF_BASE_URL = "base_url"
DEFAULT_BASE_URL = "https://api.novolt.be"

# Polling cadence. The snapshot is cheap and near-real-time; prices, plan and
# the daily aggregates only change per quarter-hour/publication, so they poll
# on a slower loop. Both are user-tunable via the options flow.
CONF_SNAPSHOT_INTERVAL = "snapshot_interval"
CONF_INSIGHTS_INTERVAL = "insights_interval"
DEFAULT_SNAPSHOT_INTERVAL_S = 30
DEFAULT_INSIGHTS_INTERVAL_S = 300
MIN_SNAPSHOT_INTERVAL_S = 10
MIN_INSIGHTS_INTERVAL_S = 60
MAX_INTERVAL_S = 3600

# Energy accumulation: a gap between two snapshot samples larger than this is
# not integrated (the site was offline / HA was down) — we never fabricate the
# energy that may or may not have flowed in between.
ENERGY_MAX_GAP_S = 600.0

BATTERY_COMMANDS = ["idle", "force_charge", "force_discharge"]

APP_URL = "https://app.novolt.be"
