"""
Load weather data and compute a daily risk score (0-3) based on
temperature, precipitation, and relative humidity.
"""
import pandas as pd
from pathlib import Path

WEATHER_FILE = Path(__file__).parent.parent.parent / "Downloads" / "SWMAC Project" / "4246861.xlsx"
WEATHER_CACHE = Path(__file__).parent.parent / "data" / "weather_scores.csv"

# Thresholds from SWMAC problem statement
TEMP_THRESHOLD = 70       # °F
PRECIP_WINDOW_DAYS = 7    # rolling window for precipitation
PRECIP_THRESHOLD = 0.1    # inches over the window
RH_THRESHOLD = 60         # percent


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

    # Rolling 7-day precipitation sum
    df["precip_7d"] = df["precip"].rolling(window=PRECIP_WINDOW_DAYS, min_periods=1).sum()

    # Score each component (0 or 1)
    df["score_temp"] = (df["temp"] >= TEMP_THRESHOLD).astype(int)
    df["score_precip"] = (df["precip_7d"] >= PRECIP_THRESHOLD).astype(int)
    df["score_rh"] = (df["rh"] >= RH_THRESHOLD).astype(int)

    # Combined weather risk score 0-3
    df["weather_risk"] = df["score_temp"] + df["score_precip"] + df["score_rh"]

    result = df[["date", "temp", "precip", "precip_7d", "rh", "weather_risk"]].copy()

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
