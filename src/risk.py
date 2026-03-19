"""
Compute composite risk scores for each permit.

Score formula:
    composite = base_score * weather_multiplier * time_decay

Base scores by risk class:
    HIGH   = 3  (grading, commercial new build)
    MEDIUM = 2  (multi-family, single family)
    LOW    = 1  (interior/mechanical work)

Weather multiplier: 1 + (weather_risk / 3)  → range 1.0 – 2.0

Time decay: linear from 1.0 (permit issued today) to 0.0 (365 days ago)
    Permits older than 365 days still included for historical analysis
    but get a floor decay of 0.05 so they remain visible.

Risk tiers:
    < 2   → Monitor  (green)
    2–4   → Larvicide  (yellow)
    > 4   → Adulticide  (red)
"""
import math
import pandas as pd
from datetime import date
from typing import Optional

BASE_SCORES = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
DECAY_DAYS = 365
CLUSTER_RADIUS_MILES = 1.0
CLUSTER_MIN_HIGH = 3  # number of HIGH permits within radius to trigger cluster alert


def _time_decay(permit_date: pd.Timestamp, as_of: date) -> float:
    days_old = (as_of - permit_date.date()).days
    if days_old < 0:
        return 1.0
    decay = max(0.05, 1.0 - days_old / DECAY_DAYS)
    return decay


def _weather_multiplier(weather_risk: float) -> float:
    return 1.0 + (weather_risk / 3.0)


def _haversine_miles(lat1, lon1, lat2, lon2) -> float:
    """Approximate distance in miles between two lat/lon points."""
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def score_permits(
    permits_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    as_of: Optional[date] = None,
) -> pd.DataFrame:
    """
    Returns permits_df with added columns:
        base_score, weather_risk, weather_multiplier, time_decay, composite_score, risk_tier
    """
    if as_of is None:
        as_of = date.today()

    df = permits_df.copy()

    # Join weather score by permit date (nearest match)
    weather_df = weather_df.sort_values("date")
    df["permit_date_only"] = df["date"].dt.normalize()

    weather_lookup = weather_df.set_index("date")["weather_risk"]

    def _get_weather(d):
        if pd.isna(d):
            return 1
        try:
            return int(weather_lookup.asof(d))
        except Exception:
            return 1

    df["weather_risk"] = df["permit_date_only"].apply(_get_weather)
    df["base_score"] = df["risk_class"].map(BASE_SCORES).fillna(1).astype(float)
    df["weather_multiplier"] = df["weather_risk"].apply(_weather_multiplier)
    df["time_decay"] = df["date"].apply(lambda d: _time_decay(d, as_of))
    df["composite_score"] = df["base_score"] * df["weather_multiplier"] * df["time_decay"]

    def _tier(score):
        if score < 2:
            return "Monitor"
        elif score <= 4:
            return "Larvicide"
        else:
            return "Adulticide"

    df["risk_tier"] = df["composite_score"].apply(_tier)
    df = df.drop(columns=["permit_date_only"])

    return df


def find_clusters(df: pd.DataFrame) -> list[dict]:
    """
    Find clusters of HIGH-risk permits within CLUSTER_RADIUS_MILES of each other.
    Returns list of cluster dicts with centroid and member permit IDs.
    """
    high_df = df[
        (df["risk_class"] == "HIGH") & df["lat"].notna() & df["lon"].notna()
    ].copy()

    if len(high_df) < CLUSTER_MIN_HIGH:
        return []

    clusters = []
    points = list(high_df[["permit_id", "lat", "lon"]].itertuples(index=False))
    visited = set()

    for i, p in enumerate(points):
        if p.permit_id in visited:
            continue
        neighbors = [p]
        for j, q in enumerate(points):
            if i == j or q.permit_id in visited:
                continue
            if _haversine_miles(p.lat, p.lon, q.lat, q.lon) <= CLUSTER_RADIUS_MILES:
                neighbors.append(q)

        if len(neighbors) >= CLUSTER_MIN_HIGH:
            member_ids = [n.permit_id for n in neighbors]
            for pid in member_ids:
                visited.add(pid)
            centroid_lat = sum(n.lat for n in neighbors) / len(neighbors)
            centroid_lon = sum(n.lon for n in neighbors) / len(neighbors)
            clusters.append({
                "count": len(neighbors),
                "permit_ids": member_ids,
                "centroid_lat": centroid_lat,
                "centroid_lon": centroid_lon,
            })

    return clusters


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    from ingest import load_all_permits
    from geocode import geocode_permits
    from weather_score import load_weather_scores

    permits = load_all_permits()
    permits = geocode_permits(permits, verbose=True)
    weather = load_weather_scores()
    scored = score_permits(permits, weather)
    print(scored[["permit_id", "address", "risk_class", "composite_score", "risk_tier"]].head(20).to_string())
    print("\nRisk tier counts:")
    print(scored["risk_tier"].value_counts())
