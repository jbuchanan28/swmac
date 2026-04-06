"""
Load weather data and compute a daily risk score (0-3) based on
temperature, precipitation, and relative humidity.
"""
import pandas as pd
from pathlib import Path

WEATHER_FILE = Path(__file__).parent.parent.parent / "Downloads" / "SWMAC Project" / "4246861.xlsx"
WEATHER_CACHE = Path(__file__).parent.parent / "data" / "weather_scores.csv"

# Ridge regression weights (Garrett + Claude, 2018-2025 trap data)
# Derived from standardised Ridge coefficients, weather-only features.
# Prior week mosquito count excluded (not applicable to permit scoring).
#
# Normalized absolute weights: temp 77%, humidity 16%, precip 6%, wind 1%
# Humidity is negative (higher humidity → lower risk in St. George's arid climate).
#
# Temperature scale: 0 at 65°F → 1.0 at 105°F+
# Humidity scale:    0 at 0%  → 1.0 at 80%
# Precipitation:     0 at 0"  → 1.0 at 0.5"+ (7-day rolling)
# Wind speed:        0 at 0   → 1.0 at 20 mph
TEMP_MIN = 65.0           # °F — below this, negligible mosquito activity
TEMP_MAX = 105.0          # °F — at or above this, maximum temperature contribution
PRECIP_WINDOW_DAYS = 7    # rolling window for precipitation
PRECIP_MAX = 0.5          # inches over window for full precip contribution
HUMIDITY_MAX = 80.0       # % — upper reference for humidity scaling
WIND_MAX = 20.0           # mph — upper reference for wind scaling
TEMP_WEIGHT     =  0.770  # positive: hot = more mosquitoes (Ridge-derived)
HUMIDITY_WEIGHT = -0.159  # negative: humid = fewer in arid climate (Ridge-derived)
PRECIP_WEIGHT   =  0.060  # positive: rain creates habitat (Ridge-derived)
WIND_WEIGHT     =  0.012  # positive: nearly negligible (Ridge-derived)


def load_weather_scores(use_cache: bool = True) -> pd.DataFrame:
    if use_cache and WEATHER_CACHE.exists():
        df = pd.read_csv(WEATHER_CACHE, parse_dates=["date"])
        return df

    print("Loading weather data (this may take a minute)...")
    df = pd.read_excel(WEATHER_FILE, engine="openpyxl")

    # Keep only daily summary rows
    df = df[df["REPORT_TYPE"].str.strip() == "SOD"].copy()

    df["date"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Extract relevant columns, coerce to numeric
    df["temp"] = pd.to_numeric(df["DailyAverageDryBulbTemperature"], errors="coerce")
    df["precip"] = pd.to_numeric(df["DailyPrecipitation"], errors="coerce").fillna(0)
    df["rh"] = pd.to_numeric(df["DailyAverageRelativeHumidity"], errors="coerce")
    df["wind"] = pd.to_numeric(df["DailyAverageWindSpeed"], errors="coerce").fillna(0)

    # Rolling 7-day precipitation sum
    df["precip_7d"] = df["precip"].rolling(window=PRECIP_WINDOW_DAYS, min_periods=1).sum()

    # Continuous feature scores (0.0 – 1.0 each)
    df["score_temp"]    = ((df["temp"] - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)).clip(0, 1)
    df["score_precip"]  = (df["precip_7d"] / PRECIP_MAX).clip(0, 1)
    # Humidity: use median fill; if entirely missing fall back to 0 (neutral — no contribution)
    _rh_median = df["rh"].median()
    df["score_humidity"]= (df["rh"].fillna(0 if pd.isna(_rh_median) else _rh_median) / HUMIDITY_MAX).clip(0, 1)
    df["score_wind"]    = (df["wind"] / WIND_MAX).clip(0, 1)

    # Ridge-derived weighted weather risk index (0.0 – 1.0)
    # Humidity term is negative: higher humidity reduces risk in St. George's arid climate.
    df["weather_risk"] = (
        TEMP_WEIGHT     * df["score_temp"]
        + HUMIDITY_WEIGHT * df["score_humidity"]
        + PRECIP_WEIGHT   * df["score_precip"]
        + WIND_WEIGHT     * df["score_wind"]
    ).clip(0, 1).round(4)

    result = df[["date", "temp", "precip", "precip_7d", "rh", "wind", "weather_risk"]].copy()

    WEATHER_CACHE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(WEATHER_CACHE, index=False)
    print(f"Weather scores saved: {len(result)} daily records")

    return result


def get_score_for_date(scores_df: pd.DataFrame, target_date: pd.Timestamp) -> int:
    """Return the weather risk score for a specific date (or nearest available)."""
    row = scores_df[scores_df["date"] == target_date]
    if not row.empty:
        return int(row.iloc[0]["weather_risk"])
    # fallback: nearest date
    idx = (scores_df["date"] - target_date).abs().idxmin()
    return int(scores_df.loc[idx, "weather_risk"])


if __name__ == "__main__":
    scores = load_weather_scores(use_cache=False)
    print(f"Date range: {scores['date'].min().date()} to {scores['date'].max().date()}")
    print(f"Average weather risk score: {scores['weather_risk'].mean():.2f}")
    print(scores[["date", "temp", "precip_7d", "rh", "weather_risk"]].tail(10).to_string())
