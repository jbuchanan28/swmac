"""
SWMAC Mosquito Risk Prediction System
Usage:
    python main.py                        # full run, alerts for last 30 days
    python main.py --since 2025-01-01     # filter permits from this date forward
    python main.py --days 60              # show alerts for last 60 days
    python main.py --no-geocode           # skip geocoding (use cache only)
    python main.py --no-map               # skip map generation
"""
import argparse
import sys
import subprocess
from pathlib import Path
from datetime import date

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ingest import load_all_permits
from geocode import geocode_permits
from weather_score import load_weather_scores
from risk import score_permits, find_clusters
from map_builder import build_map
from alerts import print_alerts


def main():
    parser = argparse.ArgumentParser(description="SWMAC Mosquito Risk System")
    parser.add_argument("--since", type=str, default=None,
                        help="Only include permits issued on or after YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=30,
                        help="Number of days back to show in console alerts (default: 30)")
    parser.add_argument("--no-geocode", action="store_true",
                        help="Skip Nominatim lookups; use cached coordinates only")
    parser.add_argument("--no-map", action="store_true",
                        help="Skip map generation")
    args = parser.parse_args()

    print("━" * 60)
    print("  SWMAC Mosquito Risk Prediction System")
    print("━" * 60)

    # 1. Load permits
    print("\n[1/5] Loading permit data...")
    permits = load_all_permits()
    print(f"      {len(permits)} permits loaded")

    if args.since:
        since_dt = date.fromisoformat(args.since)
        permits = permits[permits["date"].dt.date >= since_dt]
        print(f"      Filtered to {len(permits)} permits since {args.since}")

    # 2. Geocode
    if args.no_geocode:
        print("\n[2/5] Geocoding: using cache only (--no-geocode flag set)")
        from geocode import _load_cache
        import pandas as pd
        cache = _load_cache()
        permits = permits.copy()
        permits["lat"] = permits["address"].map(lambda a: cache.get(a, (None, None))[0])
        permits["lon"] = permits["address"].map(lambda a: cache.get(a, (None, None))[1])
    else:
        print("\n[2/5] Geocoding addresses (new addresses only — cached ones are instant)...")
        permits = geocode_permits(permits, verbose=True)

    # 3. Weather scores
    print("\n[3/5] Loading weather risk scores...")
    weather = load_weather_scores(use_cache=True)
    print(f"      {len(weather)} daily weather records loaded")

    # 4. Risk scoring
    print("\n[4/5] Computing risk scores...")
    scored = score_permits(permits, weather)
    clusters = find_clusters(scored)
    print(f"      Scored {len(scored)} permits — {len(clusters)} cluster(s) detected")

    # 5. Output
    print("\n[5/5] Generating output...\n")

    # Console alerts
    print_alerts(scored, clusters, days=args.days)

    # Map
    if not args.no_map:
        map_path = build_map(scored, clusters)
        print(f"\nMap saved to: {map_path}")
        # Auto-open on macOS
        try:
            subprocess.Popen(["open", str(map_path)])
        except Exception:
            pass

    print("\nDone.")


if __name__ == "__main__":
    main()
