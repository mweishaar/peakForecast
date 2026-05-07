# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration (`custom_components/peak_forecast/`) that scrapes Capital Electric Cooperative's peak-forecast page and exposes the 7-day, 30-min-resolution grid as native HA entities. Single-instance, polling-based, HACS-deliverable.

Targeted runtime is HA Container; users may not have shell access. Entity renames orphan recorder history, so prefer letting users rename via the HA UI rather than changing `translation_key` values or device names.

## Commands

```bash
# One-time dev setup (no HA install required for tests)
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Run the full test suite
pytest

# Run a single test
pytest tests/test_parser.py::test_total_slot_count -v

# Refresh the test fixture from the live page (overwrites; update test_parser.py FIXTURE if you rename)
curl -s https://capitalelec.com/peak-forecast -o tests/fixtures/page-$(date +%Y-%m-%d).html
```

No build step. `ruff` config exists in `pyproject.toml` but isn't wired into CI.

## Architecture: two layers, separated on purpose

**1. Pure parser layer.** `parser.py` and `const.py` have no HA imports — only `bs4` and stdlib. `parse_html(html, fetched_at=…)` returns a frozen `ForecastSnapshot(fetched_at, slots: tuple[Slot, ...])` with all datetimes UTC-aware. This is the unit-tested core; keep HA out of it.

**2. HA integration layer.** `__init__.py`, `coordinator.py`, `sensor.py`, `binary_sensor.py`, `config_flow.py`. The `PeakForecastCoordinator` (a `DataUpdateCoordinator[ForecastSnapshot]`) polls every N minutes via HA's pooled `httpx_client` and stores the snapshot. Entities derive their values lazily.

**Why entities subscribe to a per-minute clock tick:** the coordinator only refreshes every ~15 min, but "the slot under `now()`" changes every 30 min. Entities depending on current time (`current_level`, `today_max`, `next_high_*`, `high_hours_today`, both binary sensors) call `async_track_time_change(..., second=0)` in `async_added_to_hass` and `async_write_ha_state` on each tick. The `forecast_grid` sensor doesn't tick — its state is the fetch time and its 224-slot grid lives in `extra_state_attributes` to feed the future-forecast Lovelace card.

## Test setup gotcha

`tests/conftest.py` installs a **synthetic `peak_forecast` package** that bypasses the real `__init__.py`. This is required because the real `__init__.py` imports `homeassistant.*`, which isn't (and shouldn't be) installed in the test venv. The shim makes `parser.py` / `const.py` importable while their relative imports (`from .const import …`) keep working.

If you add a new HA-free module that needs testing, append it to the `for submodule in ("const", "parser")` loop in `conftest.py`. Don't try to replace the shim with a plain `sys.path` insert — Python will run the real `__init__.py` and the import will fail.

## Domain detail: waiver periods are all-clears

`data-is-waiver=true` cells on the source page mean Capital has officially **exempted** the typical peak-shaving window for that day — they are an all-clear, not an alert. Empirically every waiver cell sits at `data-value=0` and is never a downgrade. The `binary_sensor.peak_forecast_waiver_active` is therefore the *inverse* of a peak event for automation purposes. Never describe waivers as peak alerts in code, comments, README, or entity descriptions.

## Entity ID quirk worth knowing

`_attr_has_entity_name = True` + a `translation_key` makes HA compute `entity_id` as `<platform>.<device_slug>_<friendly_name_slug>`. With device name "Peak Forecast" and entity friendly name "Forecast grid", you get `sensor.peak_forecast_forecast_grid` (the word "forecast" doubles up). All Lovelace YAMLs in `lovelace/` and the entity table in `README.md` use these computed IDs — keep them in sync if you change either the device name or any translation `name` value. Renaming `translation_key` values orphans recorder history; the safe path is letting users rename via the HA UI, not changing keys.

