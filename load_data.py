"""Load the cached crawler outputs under data/raw/ into tidy DataFrames (no API calls).

Usage:
    from load_data import load_all
    d = load_all()
    d["pm25"], d["weather"], d["firms"]["VIIRS_SNPP_SP"], ...
"""
from pathlib import Path

import pandas as pd

RAW = Path(__file__).parent / "data" / "raw"
TZ = "Asia/Singapore"


def to_sgt(s):
    """Parse timestamps (any offset) and convert to Asia/Singapore."""
    return pd.to_datetime(s, utc=True).dt.tz_convert(TZ)


def load_pm25(raw=RAW, keep_updated=False, start=None, end=None):
    """Hourly, hour-ending PM2.5 per region (long form) and the region coordinates.

    start/end (YYYY-MM-DD, inclusive) keep only those `date` values, as if only that window had been crawled.
    """
    raw = Path(raw)
    files = sorted(f for f in raw.glob("pm25_*_*.csv") if f.name != "pm25_regions.csv")
    if not files:
        raise FileNotFoundError(f"no pm25_*.csv files in {raw}")
    pm = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).drop_duplicates()
    pm = pm[pm["date"].between(start or "0000", end or "9999")]
    pm["timestamp"] = to_sgt(pm["timestamp"])
    # updatedTimestamp is a back-fill date and must not be used as a feature
    if keep_updated:
        pm["updatedTimestamp"] = to_sgt(pm["updatedTimestamp"])
    else:
        pm = pm.drop(columns="updatedTimestamp")
    pm = pm.sort_values(["timestamp", "region"]).reset_index(drop=True)
    regions = pd.read_csv(raw / "pm25_regions.csv")
    return pm, regions


def load_weather(raw=RAW, endpoints=None, start=None, end=None):
    """1-minute (rainfall: 5-minute) station readings in long form, plus station metadata.

    Wind speed is in knots; wind direction is degrees *from* (aggregate with a vector mean).
    start/end (YYYY-MM-DD, inclusive) select the per-day files, so a short window loads quickly.
    """
    root = Path(raw) / "weather"
    dirs = [root / e for e in endpoints] if endpoints else sorted(p for p in root.iterdir() if p.is_dir())
    readings, stations = [], []
    for d in dirs:
        in_window = lambda f: (start or "0000") <= f.name[:10] <= (end or "9999")
        readings += [pd.read_csv(f) for f in sorted(d.glob("*.csv.gz")) if in_window(f)]
        stations += [pd.read_csv(f) for f in sorted(d.glob("*_stations.csv")) if in_window(f)]
    if not readings:
        raise FileNotFoundError(f"no weather files under {root}")
    wx = pd.concat(readings, ignore_index=True)
    wx["timestamp"] = to_sgt(wx["timestamp"])
    wx = wx.sort_values(["variable", "timestamp", "stationId"]).reset_index(drop=True)
    sta = (pd.concat(stations, ignore_index=True)
             .drop_duplicates(["stationId", "variable"])
             .drop(columns="date")
             .reset_index(drop=True))
    return wx, sta


def load_firms(raw=RAW, sources=None, include_empty=False, start=None, end=None):
    """FIRMS detections, one DataFrame per source (MODIS and VIIRS schemas differ).

    acq_date/acq_time are UTC; adds acq_datetime_utc and acq_datetime_sgt.
    start/end (YYYY-MM-DD, inclusive) filter on the UTC acq_date, the same way the crawl requests days.
    """
    out = {}
    for f in sorted((Path(raw) / "firms").glob("*.csv")):
        source = f.stem.rsplit("_", 2)[0]  # e.g. VIIRS_SNPP_SP_2023-09-15_2023-10-31 -> VIIRS_SNPP_SP
        if sources and source not in sources:
            continue
        df = pd.read_csv(f)
        df = df[df["acq_date"].between(start or "0000", end or "9999")] if len(df) else df
        if df.empty and not include_empty:
            continue
        hhmm = df["acq_time"].astype(int).astype(str).str.zfill(4)
        df["acq_datetime_utc"] = pd.to_datetime(df["acq_date"] + " " + hhmm, format="%Y-%m-%d %H%M", utc=True)
        df["acq_datetime_sgt"] = df["acq_datetime_utc"].dt.tz_convert(TZ)
        out[source] = pd.concat([out[source], df], ignore_index=True) if source in out else df
    return out


def load_all(raw=RAW, start=None, end=None):
    """Everything in the cache, optionally restricted to the dates start..end (inclusive)."""
    pm, regions = load_pm25(raw, start=start, end=end)
    wx, sta = load_weather(raw, start=start, end=end)
    return {
        "pm25": pm,
        "pm25_regions": regions,
        "weather": wx,
        "weather_stations": sta,
        "firms": load_firms(raw, start=start, end=end),
    }


def _summary(name, df, time_col):
    t = df[time_col] if len(df) else None
    span = f"{t.min()} -> {t.max()}" if t is not None else "empty"
    print(f"{name:<22} {df.shape[0]:>9,} rows x {df.shape[1]:>2} cols  {span}")


if __name__ == "__main__":
    d = load_all()
    _summary("pm25", d["pm25"], "timestamp")
    print(f"{'':<22} regions: {sorted(d['pm25']['region'].unique())}")
    _summary("weather", d["weather"], "timestamp")
    print(d["weather"].groupby("variable")["readingUnit"].first().to_string())
    print(f"{'weather_stations':<22} {len(d['weather_stations'])} station-variable pairs")
    for src, df in d["firms"].items():
        _summary(f"firms/{src}", df, "acq_datetime_sgt")
