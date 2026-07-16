# AGENTS.md

See `CLAUDE.md` for full architecture docs. This file covers only facts an agent would likely miss without help.

## Dev commands

```bash
# Setup (no HA install required)
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Run all tests (pytest only, no CI)
pytest
pytest tests/test_parser.py::test_total_slot_count -v  # single test

# Refresh fixture from live page
curl -s https://capitalelec.com/peak-forecast -o tests/fixtures/page-$(date +%Y-%m-%d).html
```

## Critical gotchas

- **Test conftest installs a synthetic package** — `tests/conftest.py` creates a fake `peak_forecast` module to bypass the real `__init__.py` (which imports `homeassistant.*`). If you add a new HA-free module, append it to the `for submodule in ("const", "parser")` loop in `conftest.py`. Don't use `sys.path` tricks.
- **Parser layer must stay HA-free** — `parser.py` and `const.py` must never import from `homeassistant.*`. Only `bs4` and stdlib allowed.
- **Waivers = all-clear, not alert** — `data-is-waiver=true` means Capital exempted that day's peak-shaving window. Never describe waivers as alerts.
- **Entity ID doubling** — `_attr_has_entity_name = True` + `translation_key` produces IDs like `sensor.peak_forecast_forecast_grid` (word doubles). Changing `translation_key` orphans recorder history; let users rename via HA UI instead.
- **Clock tick pattern** — Coordinator polls every ~15 min, but slot boundaries change every 30 min. Entities that depend on current time (`current_level`, `today_max`, `next_high_*`, `high_hours_today`, both binary sensors) subscribe to `async_track_time_change(..., second=0)` for per-minute state writes. The `forecast_grid` sensor does not tick.
- **Single-instance only** — Config flow enforces `single_instance_allowed`. No multi-instance support.

## Architecture (brief)

Two layers:
1. **`parser.py` + `const.py`** — Pure parsing, no HA. `parse_html(html, fetched_at=…)` → frozen `ForecastSnapshot(fetched_at, slots)` with UTC-aware datetimes. Unit-tested.
2. **`coordinator.py`, `sensor.py`, `binary_sensor.py`, `config_flow.py`, `__init__.py`** — HA integration. `PeakForecastCoordinator(DataUpdateCoordinator[ForecastSnapshot])` polls via HA's `httpx_client`.

Domain: `peak_forecast`. Platforms: `sensor`, `binary_sensor`. The grid spans 7 days × 32 periods (06:00–22:00 local, 30-min slots) = 224 slots, carried in `forecast_grid` sensor attributes.

## Fixtures

Tests use a captured fixture at `tests/fixtures/page-<YYYY-MM-DD>.html`. After refreshing, update the fixture filename in `test_parser.py` if you rename it, and re-check slot-count assertions (currently expects 224 slots, 84 waiver cells from the 2026-05-06 capture).

## ruff

Config in `pyproject.toml` (line-length 100, py311 target) but no CI hook — run manually.
