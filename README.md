# AWEKAS for Home Assistant

![Validate](https://github.com/awekas/ha-awekas/actions/workflows/validate.yml/badge.svg)
![Tests](https://github.com/awekas/ha-awekas/actions/workflows/tests.yml/badge.svg)

Weather data of your own AWEKAS weather station in Home Assistant.

This integration is developed and maintained by AWEKAS GmbH, the operator of the AWEKAS weather network ([www.awekas.at](https://www.awekas.at)).
It reads the data of your own weather station from the AWEKAS Stations API.

## Requirements

- Home Assistant 2026.2 or newer (the AWEKAS icon is shown from 2026.3)
- a weather station registered at AWEKAS and its API key (the Stations API is available for every registered station)
- for the forecast: an active AWEKAS **Stationsweb** subscription

## Installation

[![Open your Home Assistant instance and show the AWEKAS repository.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=awekas&repository=ha-awekas&category=integration)

The button opens the AWEKAS repository directly in your own Home Assistant. Without the button:

### Marketplace (Home Assistant 2026.11 and newer)

1. **Settings → Marketplace**.
2. Search for **AWEKAS** and install it.
3. If Home Assistant asks for a restart, restart it via **Settings → System → Repairs**.

### HACS (Home Assistant 2026.10 and older)

1. Open **HACS** in the sidebar.
2. Search for **AWEKAS** and select **Download**.
3. Restart Home Assistant.

### Manual

Download the latest [release](https://github.com/awekas/ha-awekas/releases), copy the folder `custom_components/awekas` into the `custom_components` folder of your Home Assistant configuration directory and restart Home Assistant. Manual installations are not updated automatically.

## Configuration

**Settings → Devices & services → Add integration → AWEKAS**, then enter your API key from [my.awekas.at](https://my.awekas.at).
The key is checked with one request; the same station cannot be added twice.

Options (**Configure** on the integration card):

| Option | Description |
|---|---|
| Request interval | Seconds between two requests. Minimum 60 s, default 60 s. |
| Language | Language of the forecast texts. Default: Home Assistant system language (de, en, es, it, fr, nl, pl; otherwise English). |

If the key becomes invalid, the integration stops querying and Home Assistant asks you to enter a new key.

## Entities

| Entity | Content |
|---|---|
| Weather | current conditions and the daily forecast for today and the next five days (see below) |
| Sensors | temperature, dew point, wind chill, humidity, pressure and tendency, wind, gusts, rain, rain rate, solar radiation, UV, sunshine duration, soil temperature and moisture, leaf wetness, indoor values, air quality, daily minimum/maximum values |
| Binary sensors | raining, AWEKAS Plus active, Stationsweb active |
| Diagnostics | time of the last measurement, Stationsweb valid until |

The current condition of the weather entity is taken from the condition reported by the station. If the station reports none, precipitation measured by the station is shown (rain, or snow at about 0 °C and below); otherwise today's forecast is used, with forecast precipitation shown as "cloudy" while the station measures none.

Only sensors your station actually has are created: AWEKAS always delivers all fields, a field without value (null) means the station has no such sensor. Sensors that start delivering values are added automatically. Once created, a sensor is kept: while it has no value it shows unknown, so entity IDs, names, areas and history are never lost.
The times of the daily minimum/maximum values are available as sensors, but disabled by default.
Units are converted automatically to the unit system of your Home Assistant (for example °F or mph).

## Fair use of the AWEKAS API

The AWEKAS Stations API allows 240 requests per hour and 2 requests per second. The integration stays well below these limits and protects the AWEKAS servers:

- never more than one request at a time and never more often than every 60 seconds
- ±10 % jitter so that many installations do not query at the same moment
- station data is read only once a day
- on connection or server errors the interval is increased step by step (5, 10, 20, 40, max. 60 min)
- if the quota is exceeded the integration waits 15 minutes; a `Retry-After` header is respected
- with an invalid key the integration stops querying until a new key is entered

## Privacy and security

- The API key is only sent to `https://api.awekas.at` and is never written to the log or to diagnostics files.
- Like all Home Assistant integrations, the key is stored in the Home Assistant configuration (`.storage`).
- No third-party libraries: the integration uses the HTTP client of Home Assistant.

## Reporting problems

Please report problems as an [issue](https://github.com/awekas/ha-awekas/issues) and attach the diagnostics file:
**Settings → Devices & services → AWEKAS → ⋮ → Download diagnostics**.
It contains the raw data of your station, but neither your API key nor the exact position.

## Changelog

### 0.1.1 (2026-11-24)

- the time zone of the station is resolved once without blocking the event loop
- entities are no longer removed: a sensor without value shows unknown and keeps its entity ID, name, area and history
- after a failed station request the station data is requested again after 15 minutes

### 0.1.0 (2026-11-22)

- first version: current values, daily values, forecast, station data

## License

MIT License, Copyright (c) 2026 AWEKAS GmbH
