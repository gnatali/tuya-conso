# Tuya consumption history extraction (PC321-W-TY)

Retrieves the electricity consumption history of a Tuya meter from the
**Statistics service** of the Tuya cloud (daily / monthly), without
modifying the installation. This is the same data source that feeds the
chart shown in the Smart Life app — so it's kept long-term, unlike raw
device logs which are limited to 7 days.

## Requirements

- Python 3.10+ (tested on Debian / WSL2)
- A cloud project on the **Tuya IoT Platform** with the Smart Life account
  linked (*IoT Core* and *Smart Home Basic Service* APIs authorized)
- The project credentials: `Access ID`, `Access Secret`, and the meter's
  `Device ID`

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

On the first run, leave `ENERGY_CODE` empty in `.env`: the script
auto-detects the energy code via the `/statistics` endpoint and prints the
list of available quantities.

### Outputs

- `daily_consumption_history.csv` — columns `date; kWh`
- `monthly_consumption_history.csv` — columns `month; kWh`

`;` delimiter for direct import into Excel (French locale).

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
├── requirements.txt
├── setup.sh
├── .env.example
├── .gitignore
├── config.py                     # loads config from .env
└── extract_tuya_consumption.py   # main script
```
