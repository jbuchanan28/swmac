"""
Geocode permit addresses to (lat, lon) using Nominatim with local CSV cache.
Processes in batches and saves progress so it can resume after interruption.
"""
import time
import pandas as pd
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

CACHE_FILE = Path(__file__).parent.parent / "data" / "geocoded_permits.csv"
CITY_SUFFIX = ", St. George, UT, USA"
RATE_LIMIT_SECONDS = 1.1  # Nominatim ToS: max 1 req/sec

# Bounding box for the greater St. George / Washington County, UT area
LAT_MIN, LAT_MAX = 36.8, 37.4
LON_MIN, LON_MAX = -114.2, -113.2


def _in_bounds(lat, lon) -> bool:
    if lat is None or lon is None:
        return False
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        df = pd.read_csv(CACHE_FILE)
        return dict(zip(df["address"], zip(df["lat"], df["lon"])))
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"address": addr, "lat": lat, "lon": lon} for addr, (lat, lon) in cache.items()]
    pd.DataFrame(rows).to_csv(CACHE_FILE, index=False)


def geocode_permits(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Add 'lat' and 'lon' columns to df. Uses cache; only hits Nominatim for
    addresses not yet cached. Saves cache after every 50 new lookups.
    """
    geolocator = Nominatim(user_agent="swmac_mosquito_risk_v1")
    cache = _load_cache()

    unique_addresses = df["address"].dropna().unique()
    uncached = [a for a in unique_addresses if a not in cache]

    if verbose:
        print(f"Addresses to geocode: {len(uncached)} new / {len(unique_addresses)} total")
        if uncached:
            est_minutes = len(uncached) * RATE_LIMIT_SECONDS / 60
            print(f"Estimated time for new lookups: {est_minutes:.0f} minutes")

    for i, address in enumerate(uncached):
        query = address + CITY_SUFFIX
        try:
            location = geolocator.geocode(query, timeout=10)
            if location and _in_bounds(location.latitude, location.longitude):
                cache[address] = (location.latitude, location.longitude)
            else:
                # try without city suffix as fallback
                location = geolocator.geocode(address, timeout=10)
                if location and _in_bounds(location.latitude, location.longitude):
                    cache[address] = (location.latitude, location.longitude)
                else:
                    cache[address] = (None, None)
        except (GeocoderTimedOut, GeocoderUnavailable):
            cache[address] = (None, None)

        time.sleep(RATE_LIMIT_SECONDS)

        if verbose and (i + 1) % 50 == 0:
            matched = sum(1 for v in cache.values() if v[0] is not None)
            print(f"  Progress: {i+1}/{len(uncached)} — {matched} total matched")
            _save_cache(cache)

    _save_cache(cache)

    df = df.copy()
    df["lat"] = df["address"].map(lambda a: cache.get(a, (None, None))[0])
    df["lon"] = df["address"].map(lambda a: cache.get(a, (None, None))[1])

    total = len(df)
    matched = df["lat"].notna().sum()
    if verbose:
        print(f"Geocoded: {matched}/{total} addresses ({matched/total*100:.1f}%)")

    return df


if __name__ == "__main__":
    from ingest import load_all_permits
    permits = load_all_permits()
    geocoded = geocode_permits(permits)
    print(geocoded[["permit_id", "address", "lat", "lon"]].head(10).to_string())
