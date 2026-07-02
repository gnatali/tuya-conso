#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_tuya_consumption.py
----------------------------
Extracts the consumption history of a Tuya meter (e.g. PC321-W-TY) from the
Tuya cloud Statistics service, without modifying the existing installation.

The Statistics service aggregates data by day / week / month and keeps it
long-term (it's what feeds the chart in the Smart Life app), unlike raw
device logs which are limited to 7 days.

Configuration: see the .env file (template: .env.example).
Outputs:
    - daily_consumption_history.csv     (date; kWh)
    - monthly_consumption_history.csv   (month; kWh)
"""

import csv
import sys
import datetime as dt

try:
    import tinytuya
except ImportError:
    sys.exit("TinyTuya is not installed. Activate the venv then: pip install -r requirements.txt")

import config


# =============================================================================
# CONNECTION
# =============================================================================

def connect():
    return tinytuya.Cloud(
        apiRegion=config.API_REGION,
        apiKey=config.API_KEY,
        apiSecret=config.API_SECRET,
        apiDeviceID=config.DEVICE_ID,
    )


def call_api(cloud, url, query=None):
    """Signed GET call. Returns 'result' or raises an explicit error.

    Query parameters MUST go through `query` (dict), never be concatenated
    by hand into `url`: Tuya signs the request by sorting parameters
    alphabetically by key (new signing algorithm), and TinyTuya only does
    this if `query` is a dict. A different order (e.g. code/start_day/end_day
    instead of code/end_day/start_day) causes a silent 1004 "sign invalid"
    failure — confirmed by direct testing on 2026-07-02.
    """
    resp = cloud.cloudrequest(url, query=query)
    if not isinstance(resp, dict):
        raise RuntimeError(f"Unexpected response: {resp!r}")

    if resp.get("success"):
        return resp.get("result")

    code = resp.get("code")
    msg = resp.get("msg", "")
    hint = {
        1004: "Invalid signature: check ACCESS_ID / ACCESS_SECRET and the region.",
        1106: "Permission denied: link the app account to the project (Devices tab).",
        1010: "Invalid or expired token (TinyTuya normally renews it automatically).",
        28841105: "API not authorized: subscribe to/authorize IoT Core + Smart Home Basic.",
        28841002: "IoT Core subscription expired: extend the trial period.",
        2007: "Statistics not enabled for this product (Tuya PID/DP support ticket).",
        1108: "Invalid URI: check the endpoint path being called.",
        28841101: "API not subscribed: subscribe to the Statistics service (Cloud > Cloud Services) in addition to IoT Core / Smart Home Basic.",
    }.get(code, "")
    raise RuntimeError(f"Tuya error {code}: {msg}. {hint}".strip())


# =============================================================================
# ENERGY QUANTITY DISCOVERY
# =============================================================================

def detect_energy_quantity(cloud):
    """Returns (code, stat_type) for the "energy" quantity.

    `stat_type` (e.g. "minux") is returned by /all-statistic-type for each
    code and MUST be passed back as-is to the /statistics/days and
    /statistics/months calls: without it, Tuya still replies success=True
    but with "0.00" values for every date (no explicit error) — confirmed
    by direct testing on 2026-07-02.
    """
    print(">> Detecting available statistic quantities...")
    res = call_api(cloud, f"/v1.0/devices/{config.DEVICE_ID}/all-statistic-type")
    if not res:
        raise RuntimeError("No statistics available for this device.")

    quantities = {
        item.get("code"): item.get("stat_type")
        for item in res if isinstance(item, dict) and item.get("code")
    }
    print("   Quantities found:",
          ", ".join(f"{c} ({t})" for c, t in quantities.items()) or "(none)")

    if config.ENERGY_CODE:
        if config.ENERGY_CODE not in quantities:
            raise RuntimeError(
                f"ENERGY_CODE={config.ENERGY_CODE!r} not found among: "
                f"{list(quantities)}"
            )
        return config.ENERGY_CODE, quantities[config.ENERGY_CODE]

    for preferred in ("add_ele", "EnergyConsumed", "electricity",
                       "total_forward_energy", "forward_energy_total", "energy"):
        if preferred in quantities:
            print(f"   -> energy code selected: {preferred}")
            return preferred, quantities[preferred]

    for c, t in quantities.items():
        if c and ("ele" in c.lower() or "energy" in c.lower()):
            print(f"   -> energy code guessed: {c}")
            return c, t

    raise RuntimeError(
        "Could not automatically identify the energy code. "
        f"Pick one from: {list(quantities)} and set ENERGY_CODE in .env."
    )


# =============================================================================
# DAILY EXTRACTION (month by month)
# =============================================================================

def monthly_windows(start, end):
    current = start.replace(day=1)
    while current <= end:
        next_month = (current.replace(day=28) + dt.timedelta(days=7)).replace(day=1)
        yield current, min(next_month - dt.timedelta(days=1), end)
        current = next_month


def extract_daily(cloud, code, stat_type):
    print("\n>> DAILY extraction...")
    rows = []
    url = f"/v1.0/devices/{config.DEVICE_ID}/statistics/days"
    for a, b in monthly_windows(config.INSTALL_DATE, dt.date.today()):
        query = {"code": code, "start_day": f"{a:%Y%m%d}", "end_day": f"{b:%Y%m%d}"}
        if stat_type:
            query["stat_type"] = stat_type
        try:
            res = call_api(cloud, url, query=query)
        except RuntimeError as e:
            print(f"   {a:%Y-%m} : ERROR ({e})")
            continue
        days = (res or {}).get("days", {}) if res else {}
        for day, value in days.items():
            rows.append((day, value))
        if days:
            print(f"   {a:%Y-%m} : {len(days)} days")
    rows.sort()
    return rows


# =============================================================================
# MONTHLY EXTRACTION (year by year: Tuya constraint)
# =============================================================================

def extract_monthly(cloud, code, stat_type):
    print("\n>> MONTHLY extraction...")
    rows = []
    url = f"/v1.0/devices/{config.DEVICE_ID}/statistics/months"
    for year in range(config.INSTALL_DATE.year, dt.date.today().year + 1):
        query = {"code": code, "start_month": f"{year}01", "end_month": f"{year}12"}
        if stat_type:
            query["stat_type"] = stat_type
        try:
            res = call_api(cloud, url, query=query)
        except RuntimeError as e:
            print(f"   {year} : ERROR ({e})")
            continue
        months = (res or {}).get("months", {}) if res else {}
        for m, value in months.items():
            rows.append((m, value))
        if months:
            print(f"   {year} : {len(months)} months")
    rows.sort()
    return rows


# =============================================================================
# CSV WRITING
# =============================================================================

def write_daily_csv(rows):
    with open(config.CSV_DAILY, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["date", "kWh"])
        for day, value in rows:
            d = dt.datetime.strptime(day, "%Y%m%d").date()
            w.writerow([d.isoformat(), value])
    print(f"   -> {len(rows)} rows written to {config.CSV_DAILY}")


def write_monthly_csv(rows):
    with open(config.CSV_MONTHLY, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["month", "kWh"])
        for m, value in rows:
            w.writerow([f"{m[:4]}-{m[4:6]}", value])
    print(f"   -> {len(rows)} rows written to {config.CSV_MONTHLY}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print(" Tuya consumption history extraction")
    print("=" * 60)

    cloud = connect()
    code, stat_type = detect_energy_quantity(cloud)

    daily = extract_daily(cloud, code, stat_type)
    monthly = extract_monthly(cloud, code, stat_type)

    print("\n>> Writing files...")
    if daily:
        write_daily_csv(daily)
    else:
        print("   (no daily data — check the code/period)")
    if monthly:
        write_monthly_csv(monthly)
    else:
        print("   (no monthly data)")

    print("\n" + "=" * 60)
    if daily:
        total = 0.0
        for _, v in daily:
            try:
                total += float(v)
            except (TypeError, ValueError):
                pass
        d1 = dt.datetime.strptime(daily[0][0], "%Y%m%d").date()
        d2 = dt.datetime.strptime(daily[-1][0], "%Y%m%d").date()
        print(f" Period covered: {d1} -> {d2}")
        print(f" Cumulative total (sum of daily values): {total:.2f} kWh")
    print(" Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
