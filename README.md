# Tuya consumption history extraction (PC321-W-TY)

Retrieves the electricity consumption history of a Tuya meter from the
**Statistics service** of the Tuya cloud (daily / monthly), without
modifying the installation. This is the same data source that feeds the
chart shown in the Smart Life app — so it's kept long-term, unlike raw
device logs which are limited to 7 days.

## 🔗 Related Repositories (Tasmota & Tuya Ecosystem)

This repository is part of a broader suite of tools for local smart home control with Tasmota and Tuya:

* **[tasmota32-zbgw03-matter](https://github.com/gnatali/tasmota32-zbgw03-matter)** — Custom Tasmota firmware for the eWeLink ZB-GW03 gateway supporting Zigbee (EZSP), Matter, and a built-in local Tuya driver.
* **[TasmoFlow](https://github.com/gnatali/TasmoFlow)** — No-code web interface and automation engine for Tasmota gateways to manage Zigbee and local Tuya devices.
* **[tuya-conso](https://github.com/gnatali/tuya-conso)** — Python utility to extract historical daily and monthly consumption data from Tuya energy meters.

## Requirements

- Python 3.10+ (tested on Debian / WSL2)
- A cloud project on the **Tuya IoT Platform** with the Smart Life account
  linked
- The project credentials: `Access ID`, `Access Secret`, and the meter's
  `Device ID`

### Required Tuya cloud services

All three must be subscribed **and** authorized for the project (Cloud >
Cloud Services on the Tuya IoT Platform), or calls fail with permission
errors even though credentials are correct:

| Service | Why it's needed |
|---|---|
| **IoT Core** | Base device management/authentication API — required for every call. |
| **Smart Home Basic Service** | Links the project to the Smart Life app account (Devices tab > Link App Account). |
| **Statistics service** | Serves the `/statistics/*` endpoints this script relies on. **Not self-service** — subscribe at https://www.tuya.com/vas/commodity/INTERNAL_TEST_V2 (confirmed working method; see `CLAUDE.md` if that link ever stops working — a PID/DP support ticket is the fallback path). |

### API endpoints called by the script

- `GET /v1.0/devices/{device_id}/all-statistic-type` — discovers which
  energy quantities (codes) the device reports.
- `GET /v1.0/devices/{device_id}/statistics/days` — daily history.
- `GET /v1.0/devices/{device_id}/statistics/months` — monthly history.

(`/statistics/total`, which returns a single lifetime cumulative value, is
part of the same Statistics service but isn't called by this script.)

## Installation

```bash
bash setup.sh
```

The script creates the `.venv` virtual environment, installs dependencies,
and generates a `.env` file from the template. Then edit `.env` with your
credentials:

```bash
nano .env
```

Equivalent manual installation:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Alternative: generate the config via the TinyTuya wizard

```bash
python3 -m tinytuya wizard
```

This command produces a `tinytuya.json` file (region, Access ID/Secret,
Device ID). **If present at the project root, it takes precedence over
`.env`** for the connection (region/keys/device) — `.env` is still required
for `INSTALL_DATE` and optionally `ENERGY_CODE`. This file is not committed
to version control (see `.gitignore`).

## Usage

```bash
source .venv/bin/activate
python extract_tuya_consumption.py
```

Leave `ENERGY_CODE` empty in `.env` to extract **every** quantity reported
by the device (e.g. one column per phase plus the total) — each becomes a
column in the output CSVs. Set it to extract a single quantity instead.

### Command-line options

`--install-date` and `--energy-code` override the corresponding `.env`
values for a single run, without editing the file:

```bash
python extract_tuya_consumption.py --install-date 2024-01-01 --energy-code EnergyConsumedA
```

### Outputs

- `daily_consumption_history.csv` — columns `date; <code1>; <code2>; ...`
- `monthly_consumption_history.csv` — columns `month; <code1>; <code2>; ...`

One column per extracted quantity (see `ENERGY_CODE` above). `;` delimiter
for direct import into Excel (French locale).

## Tips

- **First run**: check that the list of codes is displayed and that a
  recent month's values line up with the app before trusting the full
  history.
- **Permission error even though the app shows the chart**: the cloud
  project probably hasn't subscribed to the *IoT Core* service
  (Cloud > Cloud Services, free during the trial period).
- The `.env` file contains your secrets and is not committed to version
  control (`.gitignore`).

## Structure

```
tuya-conso/
├── README.md
├── LICENSE
├── requirements.txt
├── setup.sh
├── .env.example
├── .gitignore
├── config.py                     # loads config from .env
└── extract_tuya_consumption.py   # main script
```

## License

[MIT](LICENSE)
