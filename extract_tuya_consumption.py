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

Configuration: see the .env file (template: .env.example). Command-line
options below override the corresponding .env values when given.
If no energy code is given (neither ENERGY_CODE nor --energy-code), every
quantity reported by /all-statistic-type is extracted, one CSV column each.
Outputs:
    - daily_consumption_history.csv     (date; <code1>; <code2>; ...)
    - monthly_consumption_history.csv   (month; <code1>; <code2>; ...)
"""

import argparse
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

def select_energy_quantities(cloud):
    """Returns the list of (code, stat_type) pairs to extract.

    `stat_type` (e.g. "minux") is returned by /all-statistic-type for each
    code and MUST be passed back as-is to the /statistics/days and
    /statistics/months calls: without it, Tuya still replies success=True
    but with "0.00" values for every date (no explicit error) — confirmed
    by direct testing on 2026-07-02.

    If ENERGY_CODE is set (via .env or --energy-code), only that single
    quantity is extracted. Otherwise every quantity reported by
    /all-statistic-type is extracted (e.g. per-phase codes plus the total).
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
        print(f"   -> extracting only: {config.ENERGY_CODE}")
        return [(config.ENERGY_CODE, quantities[config.ENERGY_CODE])]

    if not quantities:
        raise RuntimeError(
            "No energy quantity detected. Set ENERGY_CODE in .env or pass --energy-code."
        )
    print(f"   -> no ENERGY_CODE set: extracting all {len(quantities)} quantities")
    return list(quantities.items())


# =============================================================================
# DAILY EXTRACTION (month by month)
# =============================================================================

def monthly_windows(start, end):
    current = start.replace(day=1)
    while current <= end:
        next_month = (current.replace(day=28) + dt.timedelta(days=7)).replace(day=1)
        yield current, min(next_month - dt.timedelta(days=1), end)
        current = next_month


def extract_daily(cloud, quantities):
    """Returns {day: {code: value}} for every (code, stat_type) in quantities."""
    print("\n>> DAILY extraction...")
    data = {}
    url = f"/v1.0/devices/{config.DEVICE_ID}/statistics/days"
    for code, stat_type in quantities:
        for a, b in monthly_windows(config.INSTALL_DATE, dt.date.today()):
            query = {"code": code, "start_day": f"{a:%Y%m%d}", "end_day": f"{b:%Y%m%d}"}
            if stat_type:
                query["stat_type"] = stat_type
            try:
                res = call_api(cloud, url, query=query)
            except RuntimeError as e:
                print(f"   {code} {a:%Y-%m} : ERROR ({e})")
                continue
            days = (res or {}).get("days", {}) if res else {}
            for day, value in days.items():
                data.setdefault(day, {})[code] = value
            if days:
                print(f"   {code} {a:%Y-%m} : {len(days)} days")
    return data


# =============================================================================
# MONTHLY EXTRACTION (year by year: Tuya constraint)
# =============================================================================

def extract_monthly(cloud, quantities):
    """Returns {month: {code: value}} for every (code, stat_type) in quantities."""
    print("\n>> MONTHLY extraction...")
    data = {}
    url = f"/v1.0/devices/{config.DEVICE_ID}/statistics/months"
    for code, stat_type in quantities:
        for year in range(config.INSTALL_DATE.year, dt.date.today().year + 1):
            query = {"code": code, "start_month": f"{year}01", "end_month": f"{year}12"}
            if stat_type:
                query["stat_type"] = stat_type
            try:
                res = call_api(cloud, url, query=query)
            except RuntimeError as e:
                print(f"   {code} {year} : ERROR ({e})")
                continue
            months = (res or {}).get("months", {}) if res else {}
            for m, value in months.items():
                data.setdefault(m, {})[code] = value
            if months:
                print(f"   {code} {year} : {len(months)} months")
    return data


# =============================================================================
# CSV WRITING
# =============================================================================

def write_daily_csv(data, codes):
    with open(config.CSV_DAILY, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["date"] + codes)
        for day in sorted(data):
            d = dt.datetime.strptime(day, "%Y%m%d").date()
            w.writerow([d.isoformat()] + [data[day].get(c, "") for c in codes])
    print(f"   -> {len(data)} rows written to {config.CSV_DAILY}")


def write_monthly_csv(data, codes):
    with open(config.CSV_MONTHLY, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["month"] + codes)
        for m in sorted(data):
            w.writerow([f"{m[:4]}-{m[4:6]}"] + [data[m].get(c, "") for c in codes])
    print(f"   -> {len(data)} rows written to {config.CSV_MONTHLY}")


# =============================================================================
# MAIN
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract Tuya meter consumption history from the cloud Statistics service."
    )
    parser.add_argument(
        "--install-date", metavar="YYYY-MM-DD",
        help="Override INSTALL_DATE from .env (start date for extraction).",
    )
    parser.add_argument(
        "--energy-code", metavar="CODE",
        help="Override ENERGY_CODE from .env (skips auto-detection).",
    )
    return parser.parse_args()


def apply_overrides(args):
    if args.install_date:
        try:
            config.INSTALL_DATE = dt.datetime.strptime(args.install_date, "%Y-%m-%d").date()
        except ValueError:
            sys.exit(f"Invalid --install-date: '{args.install_date}' (expected YYYY-MM-DD)")
    if args.energy_code:
        config.ENERGY_CODE = args.energy_code


def main():
    apply_overrides(parse_args())

    print("=" * 60)
    print(" Tuya consumption history extraction")
    print("=" * 60)

    cloud = connect()
    quantities = select_energy_quantities(cloud)
    codes = [code for code, _ in quantities]

    daily = extract_daily(cloud, quantities)
    monthly = extract_monthly(cloud, quantities)

    print("\n>> Writing files...")
    if daily:
        write_daily_csv(daily, codes)
    else:
        print("   (no daily data — check the code/period)")
    if monthly:
        write_monthly_csv(monthly, codes)
    else:
        print("   (no monthly data)")

    print("\n" + "=" * 60)
    if daily:
        all_days = sorted(daily)
        d1 = dt.datetime.strptime(all_days[0], "%Y%m%d").date()
        d2 = dt.datetime.strptime(all_days[-1], "%Y%m%d").date()
        print(f" Period covered: {d1} -> {d2}")
        for c in codes:
            total = 0.0
            for day in all_days:
                try:
                    total += float(daily[day].get(c, 0) or 0)
                except (TypeError, ValueError):
                    pass
            print(f" Cumulative total for {c} (sum of daily values): {total:.2f} kWh")
    print(" Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
