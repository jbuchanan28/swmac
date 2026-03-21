"""
Geocode permit addresses to (lat, lon) using Nominatim with local CSV cache.
Processes in batches and saves progress so it can resume after interruption.
Also supports batch geocoding via the US Census Geocoder API.
"""
import io
import time
import requests
import pandas as pd
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable, GeocoderRateLimited

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
        except GeocoderRateLimited:
            if verbose:
                print(f"  Rate limited — waiting 60s before retrying...")
            _save_cache(cache)
            time.sleep(60)
            try:
                location = geolocator.geocode(query, timeout=10)
                if location and _in_bounds(location.latitude, location.longitude):
                    cache[address] = (location.latitude, location.longitude)
                else:
                    cache[address] = (None, None)
            except Exception:
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


def census_batch_geocode(addresses: list, verbose: bool = True) -> dict:
    """
    Geocode a list of address strings using the US Census Geocoder batch API.
    Returns a dict of {address: (lat, lon)} — unmatched addresses get (None, None).
    Processes in chunks of 9,000 (API limit is 10,000).
    """
    CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
    results = {}
    chunk_size = 9000

    for chunk_start in range(0, len(addresses), chunk_size):
        chunk = addresses[chunk_start: chunk_start + chunk_size]
        if verbose:
            print(f"  Sending {len(chunk)} addresses to Census geocoder...")

        # Build CSV payload: ID, street, city, state, zip
        lines = []
        for i, addr in enumerate(chunk):
            # Addresses are like "123 MAIN ST" — append St. George, UT
            lines.append(f'{i},"{addr}","St. George","UT",""')
        payload = "\n".join(lines)

        try:
            resp = requests.post(
                CENSUS_URL,
                files={"addressFile": ("addresses.csv", payload, "text/csv")},
                data={"benchmark": "Public_AR_Current", "vintage": "Current_Current"},
                timeout=120,
            )
            resp.raise_for_status()
        except Exception as e:
            if verbose:
                print(f"  Census API error: {e}")
            for addr in chunk:
                results[addr] = (None, None)
            continue

        # Parse response CSV (fields: id, input_addr, match, match_type, matched_addr, lon_lat, tiger_id, side)
        import csv
        reader = csv.reader(io.StringIO(resp.text))
        for row in reader:
            if len(row) < 3:
                continue
            try:
                idx = int(row[0])
            except ValueError:
                continue
            addr = chunk[idx]
            match_status = row[2].strip()
            if match_status == "Match" and len(row) >= 6:
                try:
                    lon_lat = row[5].strip()
                    lon, lat = map(float, lon_lat.split(","))
                    if _in_bounds(lat, lon):
                        results[addr] = (lat, lon)
                    else:
                        results[addr] = (None, None)
                except (ValueError, IndexError):
                    results[addr] = (None, None)
            else:
                results[addr] = (None, None)

        matched = sum(1 for v in results.values() if v[0] is not None)
        if verbose:
            print(f"  Matched {matched}/{len(results)} so far")

    return results


def geocode_remaining_census(verbose: bool = True) -> None:
    """
    Find all addresses not yet in the cache and geocode them via Census batch API.
    Updates geocoded_permits.csv in place.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from ingest import load_all_permits

    df = load_all_permits()
    cache = _load_cache()

    all_addrs = df["address"].dropna().unique().tolist()
    uncached = [a for a in all_addrs if a not in cache]

    if not uncached:
        print("All addresses already cached.")
        return

    if verbose:
        print(f"{len(uncached)} addresses to geocode via Census API...")

    new_results = census_batch_geocode(uncached, verbose=verbose)
    cache.update(new_results)
    _save_cache(cache)

    matched = sum(1 for v in new_results.values() if v[0] is not None)
    if verbose:
        print(f"Done. {matched}/{len(uncached)} new addresses matched.")
        print(f"Total cached: {len(cache)}")


if __name__ == "__main__":
    from ingest import load_all_permits
    permits = load_all_permits()
    geocoded = geocode_permits(permits)
    print(geocoded[["permit_id", "address", "lat", "lon"]].head(10).to_string())
