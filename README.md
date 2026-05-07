# Peak Forecast — Home Assistant Integration

A Home Assistant custom integration that scrapes the [Capital Electric Cooperative peak forecast page](https://capitalelec.com/peak-forecast) and exposes the 7-day, 30-minute-resolution forecast grid as native HA entities. Use it to automate HVAC, water heaters, EV charging, and other heavy loads against likely peak-demand windows — and to review past forecasts and waiver periods.

> **Why this exists.** Capital Electric publishes a member-facing peak-probability grid so members can shift load away from co-op peak hours. This integration brings that grid into Home Assistant so the shifting can happen automatically.

---

## Features

- 🟢 / 🟡 / 🔴 current peak level as a Home Assistant `sensor`
- Today's max level, next high-probability window start/end, daily high-hour count
- A `binary_sensor` that turns on during high peak and another for active waivers
- Full 7-day grid carried in attributes for chart rendering
- Built-in history card; ApexCharts heatmap for the future-forecast view
- HACS-installable, no API keys, no add-ons required

## Requirements

- Home Assistant 2024.1 or newer (Container, Supervised, OS, or Core)
- Optional: [HACS](https://hacs.xyz) for one-click installs and the future-forecast card dependency

## Installation

### Option A — HACS (recommended)

1. HACS → Integrations → ⋮ → **Custom repositories**.
2. Add `https://github.com/mweishaar/peakForecast` as an *Integration*.
3. Install **Peak Forecast** from the list, then restart Home Assistant.
4. Settings → Devices & Services → **Add Integration** → search for *Peak Forecast*.

### Option B — Manual (Container install)

Copy the integration into your HA config directory:

```bash
cp -r custom_components/peak_forecast \
  /path/to/homeassistant/config/custom_components/
```

Restart HA, then add the integration via the UI.

## Configuration

The config flow asks for two values; both have working defaults:

| Field | Default | Notes |
| --- | --- | --- |
| Forecast page URL | `https://capitalelec.com/peak-forecast` | Override only if pointing at another co-op using the same Drupal grid markup. |
| Poll interval (minutes) | `15` | Min `5`. The page updates infrequently — every 15 min is plenty. |

Both are editable later under the integration's *Configure* button.

## Entities

| Entity | Type | What it does |
| --- | --- | --- |
| `sensor.peak_forecast_current_peak_level` | enum (`low`/`medium`/`high`/`unknown`) | Level for the slot containing right now. `unknown` outside 06:00–22:00 local. |
| `sensor.peak_forecast_today_s_max_level` | enum | Highest level forecast for today. |
| `sensor.peak_forecast_next_high_peak_starts` | timestamp | Start of the next high-probability window. |
| `sensor.peak_forecast_next_high_peak_ends` | timestamp | End of that contiguous window. |
| `sensor.peak_forecast_high_peak_hours_today` | hours | Count of today's high-prob 30-min slots × 0.5. |
| `sensor.peak_forecast_forecast_grid` | timestamp | State = last fetch time. **Attributes contain the full 224-slot grid** for chart cards. |
| `binary_sensor.peak_forecast_peak_active` | binary | `on` when current slot is high. |
| `binary_sensor.peak_forecast_waiver_active` | binary | `on` when current slot has a co-op waiver applied. |

(Entity IDs are auto-generated from translation keys; yours may differ slightly. Check Settings → Devices & Services → Peak Forecast.)

## Lovelace cards

Two ready-to-paste card configs live in `lovelace/`:

- **`lovelace/future-forecast-card.yaml`** — ApexCharts column chart of the next 7 days of slots, color-coded by level. Requires the [ApexCharts Card](https://github.com/RomRider/apexcharts-card) (HACS Frontend).
- **`lovelace/history-card.yaml`** — built-in `history-graph` showing recent levels and active flags. No extras required.

Add them via *Edit Dashboard → Add Card → Manual* and paste the YAML.

## Example automation

Pre-cool the house an hour before the next high-peak window starts:

```yaml
automation:
  - alias: Pre-cool before peak
    trigger:
      - platform: template
        value_template: >
          {{ as_timestamp(states('sensor.peak_forecast_next_high_peak_starts'))
             - as_timestamp(now()) | int < 3600 }}
    condition:
      - condition: state
        entity_id: binary_sensor.peak_forecast_peak_active
        state: 'off'
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.living_room
        data:
          temperature: 68

  - alias: Coast through peak
    trigger:
      - platform: state
        entity_id: binary_sensor.peak_forecast_peak_active
        to: 'on'
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.living_room
        data:
          temperature: 76
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Tests run against a captured copy of the live page in `tests/fixtures/page-2026-05-06.html`. To refresh the fixture:

```bash
curl -s https://capitalelec.com/peak-forecast -o tests/fixtures/page-$(date +%Y-%m-%d).html
```

## Limitations

- v1 only parses Capital Electric's specific Drupal grid markup. The URL is overridable but the parser will reject pages without `div.grid-cell[data-date][data-period]`.
- History is recorder-backed. If you wipe HA's recorder, you lose forecast history.
- The grid is published in 30-min slots covering 06:00–22:00 local; outside that window `current_peak_level` reports `unknown`.

## License

MIT — see `LICENSE`.
