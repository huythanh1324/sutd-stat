"""Build the hourly modelling table from the cached raw data (no API calls).

One row per forecast time t (hour-ending, Asia/Singapore). Every input uses only data
time-stamped <= t; the target is island-mean PM2.5 at t + h.

Usage:
    from load_data import load_all
    from features import build_model_table
    table = build_model_table(load_all(), h=24)
"""
import numpy as np
import pandas as pd

SG_LAT, SG_LON = 1.35, 103.82
KNOTS_TO_MS = 0.514
FIRE_SOURCE = "VIIRS_SNPP_SP"
# sector name -> bearing of its centre (degrees, measured clockwise from north, as seen from Singapore)
SECTORS = {"N": 0, "E": 90, "S": 180, "W": 270}


def hourly_grid(pm):
    """Complete hourly index covering the PM2.5 window, so missing hours become explicit NaN rows."""
    return pd.date_range(pm["timestamp"].min(), pm["timestamp"].max(), freq="h", name="timestamp")


def pm25_features(pm, grid, h):
    """Island-mean PM2.5 (only hours where all 5 regions report), its lags, and the target at t + h."""
    by_hour = pm.groupby("timestamp")["value"].agg(["mean", "size"])
    pm25_mean = by_hour["mean"].where(by_hour["size"] == 5).reindex(grid)
    return pd.DataFrame({
        "pm25_mean": pm25_mean,
        "pm25_lag0": pm25_mean,                 # value known at t (persistence input)
        "pm25_lag24": pm25_mean.shift(24),      # same hour yesterday
        "y": pm25_mean.shift(-h),               # target: PM2.5 at t + h
    }, index=grid)


def calendar_features(grid):
    hour = grid.hour
    return pd.DataFrame({
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
        "is_weekend": (grid.dayofweek >= 5).astype(int),
    }, index=grid)


def full_stations(wx):
    """Stations that report all 5 weather variables (the rest are rain gauges only)."""
    n_vars = wx.groupby("stationId")["variable"].nunique()
    return sorted(n_vars[n_vars == wx["variable"].nunique()].index)


def weather_features(wx, grid):
    """Hourly island-mean weather from the full stations.

    Same convention as `to_hourly` in data.ipynb: hour-ending labels via ceil("h"), aggregate per
    station first (mean, or sum for 5-minute rainfall), then average across stations.
    """
    w = wx[wx["stationId"].isin(full_stations(wx))].copy()
    w["hour"] = w["timestamp"].dt.ceil("h")

    def station_then_island(var, how):
        g = w[w["variable"] == var].groupby(["hour", "stationId"])["value"]
        return getattr(g, how)().groupby("hour").mean().reindex(grid)

    out = pd.DataFrame({
        "temp": station_then_island("air-temperature", "mean"),
        "rh": station_then_island("relative-humidity", "mean"),
        "rain_1h": station_then_island("rainfall", "sum"),
        "ws_ms": station_then_island("wind-speed", "mean") * KNOTS_TO_MS,
    }, index=grid)

    # wind vector per minute and station, then hourly mean of the components
    wd = w[w["variable"] == "wind-direction"].set_index(["timestamp", "stationId"])["value"]
    ws = w[w["variable"] == "wind-speed"].set_index(["timestamp", "stationId"])["value"] * KNOTS_TO_MS
    uv = pd.concat({"dir": wd, "spd": ws}, axis=1).dropna().reset_index()
    rad = np.deg2rad(uv["dir"])
    uv["u"] = -uv["spd"] * np.sin(rad)          # > 0: wind blowing towards the east
    uv["v"] = -uv["spd"] * np.cos(rad)          # > 0: wind blowing towards the north
    uv["hour"] = uv["timestamp"].dt.ceil("h")
    comp = uv.groupby(["hour", "stationId"])[["u", "v"]].mean().groupby("hour").mean().reindex(grid)
    out["u"], out["v"] = comp["u"], comp["v"]

    out["rain_24h"] = out["rain_1h"].rolling(24, min_periods=24).sum()
    return out


def fire_bearing(lat, lon):
    """Compass bearing (degrees from north) of each fire pixel as seen from Singapore."""
    dx = (lon - SG_LON) * np.cos(np.deg2rad(SG_LAT))
    dy = lat - SG_LAT
    return np.rad2deg(np.arctan2(dx, dy)) % 360


def fire_sector(bearing):
    """Four 90-degree sectors centred on N, E, S, W."""
    return pd.Series(np.select(
        [(bearing >= 315) | (bearing < 45), bearing < 135, bearing < 225],
        ["N", "E", "S"], default="W"), index=bearing.index)


def fire_features(firms, grid):
    """log(1 + summed FRP) per sector over the past 24 h, and over the 24 h before that."""
    f = firms[FIRE_SOURCE]
    f = f[(f["type"] == 0) & (f["confidence"].astype(str) != "l")].copy()
    f["sector"] = fire_sector(fire_bearing(f["latitude"], f["longitude"]))
    f["hour"] = f["acq_datetime_sgt"].dt.ceil("h")    # a detection at 10:35 counts from t = 11:00 onwards
    hourly = (f.groupby(["hour", "sector"])["frp"].sum().unstack(fill_value=0)
                .reindex(index=grid, columns=list(SECTORS), fill_value=0))
    # fires before the crawl window are unknown, so the first 24 h / 48 h of windows stay NaN
    past24 = hourly.rolling(24, min_periods=24).sum()  # labels t-23 .. t  =  detections in (t-24h, t]
    out = pd.DataFrame(index=grid)
    for s in SECTORS:
        out[f"frp_{s}_24h"] = np.log1p(past24[s])
        out[f"frp_{s}_lag1d"] = np.log1p(past24[s].shift(24))
    return out


def transport_features(fire, weather):
    """Wind speed blowing from each sector towards Singapore, and its product with that sector's fires."""
    out = pd.DataFrame(index=fire.index)
    for s, beta in SECTORS.items():
        b = np.deg2rad(beta)
        out[f"wind_from_{s}"] = (-(weather["u"] * np.sin(b) + weather["v"] * np.cos(b))).clip(lower=0)
        out[f"transport_{s}"] = fire[f"frp_{s}_24h"] * out[f"wind_from_{s}"]
    return out


def build_model_table(d, h=24):
    """Join all features on the hourly grid; `target_time` = t + h."""
    grid = hourly_grid(d["pm25"])
    pm = pm25_features(d["pm25"], grid, h)
    wx = weather_features(d["weather"], grid)
    fire = fire_features(d["firms"], grid)
    table = pd.concat([pm, calendar_features(grid), wx, fire, transport_features(fire, wx)], axis=1)
    table.insert(0, "target_time", table.index + pd.Timedelta(hours=h))

    # leakage guard: the target really is PM2.5 h hours later
    later = table["pm25_mean"].reindex(table["target_time"]).to_numpy()
    assert np.allclose(table["y"].to_numpy(), later, equal_nan=True), "target misaligned"
    return table


if __name__ == "__main__":
    from load_data import load_all
    t = build_model_table(load_all())
    print(t.shape, t.index.min(), "->", t.index.max())
    print(t.notna().sum().to_string())
