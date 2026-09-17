"""
Load historical season data from dataset Excel files for seasonal reports.

Sources (under Shrimply_Smart/dataset/):
  - feedOfSrimpDateAndAmount/*.xlsx
  - weatherForShrimpFeedingDate/open-meteo-*.xlsx
  - harvests/*.xlsx
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATASET_ROOT = Path(__file__).resolve().parents[2] / "dataset"
FEED_DIR = DATASET_ROOT / "feedOfSrimpDateAndAmount"
WEATHER_FILE = DATASET_ROOT / "weatherForShrimpFeedingDate" / "open-meteo-13.32N121.15E1m.xlsx"
HARVEST_DIR = DATASET_ROOT / "harvests"

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

_WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog",
    51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
    61: "Rain", 63: "Rain", 65: "Heavy rain",
    71: "Snow", 73: "Snow", 75: "Snow",
    80: "Rain showers", 81: "Rain showers", 82: "Heavy showers",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
}


def parse_filename_window(name: str):
    stem = Path(name).stem.replace("_normalized", "").rstrip(".")
    m = re.match(
        r"(?P<m1>[A-Za-z]+)(?P<d1>\d{1,2}),(?P<y1>\d{4})-(?P<m2>[A-Za-z]+)(?P<d2>\d{1,2}),(?P<y2>\d{4})",
        stem,
    )
    if not m:
        return None, None
    m1 = _MONTHS.get(m.group("m1").lower())
    m2 = _MONTHS.get(m.group("m2").lower())
    if not m1 or not m2:
        return None, None
    start = date(int(m.group("y1")), m1, int(m.group("d1")))
    end = date(int(m.group("y2")), m2, int(m.group("d2")))
    return start, end


def _overlap_days(a0, a1, b0, b1):
    start = max(a0, b0)
    end = min(a1, b1)
    if start > end:
        return 0
    return (end - start).days + 1


def _parse_kg(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).lower().replace(",", "").replace("kgs", "").replace("kg", "").replace("kls", "").strip()
    try:
        return float(s)
    except ValueError:
        m = re.search(r"([\d.]+)", s)
        return float(m.group(1)) if m else None


def _parse_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value, errors="coerce").date()
    except Exception:
        return None


@lru_cache(maxsize=1)
def load_daily_weather():
    """Return dict[date] -> weather fields from Open-Meteo hourly file."""
    if not WEATHER_FILE.exists():
        return {}
    raw = pd.read_excel(WEATHER_FILE, header=None)
    hdr = None
    for i in range(min(15, len(raw))):
        if str(raw.iloc[i, 0]).strip().lower() == "time":
            hdr = i
            break
    if hdr is None:
        return {}
    df = pd.read_excel(WEATHER_FILE, header=hdr)
    # Normalize column names
    colmap = {c: str(c) for c in df.columns}
    df = df.rename(columns=colmap)
    time_col = df.columns[0]
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col])

    def find_col(substrs):
        for c in df.columns:
            cl = str(c).lower()
            if all(s in cl for s in substrs):
                return c
        return None

    temp_c = find_col(["temperature_2m"]) or df.columns[1]
    hum_c = find_col(["relative_humidity"]) 
    precip_c = find_col(["precipitation"]) 
    code_c = find_col(["weather_code"])

    df["day"] = df[time_col].dt.date
    out = {}
    for day, g in df.groupby("day"):
        temp = pd.to_numeric(g[temp_c], errors="coerce").mean()
        hum = pd.to_numeric(g[hum_c], errors="coerce").mean() if hum_c else None
        precip = pd.to_numeric(g[precip_c], errors="coerce").sum() if precip_c else None
        code = None
        cond = None
        if code_c:
            modes = pd.to_numeric(g[code_c], errors="coerce").dropna()
            if len(modes):
                code = int(modes.mode().iloc[0])
                cond = _WMO.get(code, f"Code {code}")
        out[day] = {
            "temperature": round(float(temp), 2) if pd.notna(temp) else None,
            "humidity": round(float(hum), 1) if hum is not None and pd.notna(hum) else None,
            "precipitation": round(float(precip), 2) if precip is not None and pd.notna(precip) else None,
            "condition": cond,
            "weather_code": code,
        }
    return out


def load_feed_by_day(start: date, end: date):
    """Match best feed Excel by filename window; return dict[date] -> kg."""
    if not FEED_DIR.exists():
        return {}, None
    best_file = None
    best_score = -1
    for path in FEED_DIR.glob("*.xlsx"):
        if path.name.startswith("~"):
            continue
        fs, fe = parse_filename_window(path.name)
        if not fs or not fe:
            continue
        score = _overlap_days(start, end, fs, fe)
        if score > best_score:
            best_score = score
            best_file = path
    if not best_file or best_score <= 0:
        return {}, None

    df = pd.read_excel(best_file)
    date_col = next((c for c in df.columns if str(c).lower() == "date"), df.columns[0])
    feed_col = next(
        (c for c in df.columns if "total_feed" in str(c).lower() or str(c).lower() == "total"),
        None,
    )
    if feed_col is None:
        return {}, best_file.name

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    # Fix year-wrap typos using filename window (e.g. Jan written as 2024 instead of 2025)
    fs, fe = parse_filename_window(best_file.name)
    out = {}
    for _, row in df.iterrows():
        d = row[date_col].date()
        if fs and fe:
            # If date falls outside window but month/day fit end year, nudge year
            if d < fs or d > fe:
                try:
                    cand = date(fe.year if d.month <= fe.month else fs.year, d.month, d.day)
                    if fs <= cand <= fe:
                        d = cand
                except ValueError:
                    pass
        if d < start or d > end:
            continue
        kg = pd.to_numeric(row[feed_col], errors="coerce")
        if pd.isna(kg):
            continue
        out[d] = out.get(d, 0.0) + float(kg)
    return out, best_file.name


def load_harvest_record(start: date, end: date):
    """
    From harvests/*.xlsx cost sheets:
      returns {close_date, harvest_kg, stocking_date, stocks, file}
    """
    if not HARVEST_DIR.exists():
        return None
    best = None
    best_score = -1
    for path in HARVEST_DIR.glob("*.xlsx"):
        fs, fe = parse_filename_window(path.name)
        score = 0
        if fs and fe:
            score = _overlap_days(start, end, fs, fe)
        if score > best_score:
            best_score = score
            best = path
    if not best or best_score <= 0:
        return None

    df = pd.read_excel(best, header=None)
    stocking = None
    close = None
    harvest_kg = None
    stocks = None
    for _, r in df.iterrows():
        cells = list(r.tolist())
        for j, v in enumerate(cells):
            if not isinstance(v, str):
                continue
            key = v.strip().lower()
            nxt = next((x for x in cells[j + 1:] if pd.notna(x) and str(x).strip() != ""), None)
            if "stocking date" in key:
                stocking = _parse_date(nxt)
            elif "close harvest" in key:
                close = _parse_date(nxt)
            elif "actual harvest" in key:
                harvest_kg = _parse_kg(nxt)
            elif "actual stocks" in key:
                stocks = _parse_kg(nxt)  # pcs count
    # Prefer filename end date if close date looks wrong / outside window
    fs, fe = parse_filename_window(best.name)
    if close is None:
        close = fe
    elif fs and fe and (close < fs - timedelta(days=60) or close > fe + timedelta(days=120)):
        close = fe
    return {
        "file": best.name,
        "stocking_date": stocking or fs,
        "close_date": close or fe,
        "harvest_kg": harvest_kg,
        "stocks": int(stocks) if stocks is not None else None,
        "overlap_days": best_score,
    }


def build_dataset_daily_rows(start: date, end: date):
    """
    Build per-day rows from dataset files for [start, end].
    Feed kg / weather filled when present; harvest only on close date.
    """
    weather = load_daily_weather()
    feed_map, feed_file = load_feed_by_day(start, end)
    harvest = load_harvest_record(start, end)

    # Place harvest on close date when inside the season window; otherwise on season end
    harvest_day = None
    harvest_kg_total = None
    if harvest and harvest.get("harvest_kg") is not None:
        harvest_kg_total = harvest["harvest_kg"]
        close = harvest.get("close_date")
        if close and start <= close <= end:
            harvest_day = close
        else:
            harvest_day = end

    rows = []
    day = start
    while day <= end:
        w = weather.get(day)
        feed_kg = feed_map.get(day)
        harvest_kg = harvest_kg_total if harvest_day == day else None

        has_any = bool(w or feed_kg is not None or harvest_kg is not None)
        if not has_any:
            day += timedelta(days=1)
            continue

        rows.append({
            "date": day.isoformat(),
            # Pond sensors are not in these historical Excel sets
            "avg_temperature": None,
            "avg_ph": None,
            "avg_turbidity": None,
            "avg_tds": None,
            "weather_temperature": w.get("temperature") if w else None,
            "weather_condition": w.get("condition") if w else None,
            "weather_precipitation_mm": w.get("precipitation") if w else None,
            "weather_humidity": w.get("humidity") if w else None,
            "feed_kg": round(feed_kg, 2) if feed_kg is not None else None,
            "feed_events": 5 if feed_kg is not None else None,  # 5 slots/day in feed sheets
            "harvest_kg": harvest_kg,
            "_source_feed_file": feed_file,
            "_source_harvest_file": harvest.get("file") if harvest else None,
        })
        day += timedelta(days=1)

    return rows, {"feed_file": feed_file, "harvest": harvest}
