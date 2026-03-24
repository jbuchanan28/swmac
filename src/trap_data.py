"""
Load and clean SWMAC mosquito trap data from SWMACActualMosqData.xlsx.

Handles:
  - 2016-2019: WNV/WEE results stored as 'Y'/'N' columns
  - 2020-2025: WNV/WEE/SLE results stored as 'NEG'/'POS' in 'Results WNV' etc.
  - 2020 sheet: 1M empty rows stripped (only ~2,682 real rows)
  - 2023-2025: column headers are fine, schema matches 2020-2022

Site coordinates are approximate area centers — no exact lat/lon exists in the source data.
"""
import pandas as pd
from pathlib import Path

SOURCE_FILE = Path.home() / "Downloads" / "SWMAC Project" / "SWMACActualMosqData.xlsx"
CACHE_PATH  = Path(__file__).parent.parent / "data" / "trap_data_clean.csv"

YEAR_SHEETS = ["2016","2017","2018","2019","2020","2021","2022","2023","2024","2025"]

# Approximate area-center coordinates keyed by site-code prefix (uppercase)
AREA_COORDS = {
    "SGE": (37.1041, -113.5841),   # St. George
    "SCL": (37.1340, -113.6541),   # Santa Clara
    "IVI": (37.1649, -113.6794),   # Ivins
    "WAS": (37.1301, -113.5085),   # Washington City
    "LEE": (37.2394, -113.3603),   # Leeds
    "HAR": (37.1753, -113.2892),   # Hurricane
    "HUR": (37.1753, -113.2892),   # Hurricane (alt code)
    "LAV": (37.2029, -113.2734),   # LaVerkin
    "TOQ": (37.2437, -113.3014),   # Toquerville
    "VIR": (37.2167, -113.2500),   # Virgin
    "ROC": (37.1665, -113.3503),   # Rockville
    "SPR": (37.1887, -113.3273),   # Springdale
    "APV": (37.1357, -113.1269),   # Apple Valley
    "AEG": (37.1357, -113.1269),   # Apple Valley / Greendale
    "ENT": (37.5727, -113.7229),   # Enterprise
    "NHA": (37.4960, -113.3168),   # New Harmony
    "HIL": (37.0013, -112.9979),   # Hildale
    "AVA": (37.1000, -113.5500),   # Avalon (approximate)
    "SR":  (37.1041, -113.5841),   # Special Research (St. George area)
}

AREA_NAMES = {
    "SGE": "St. George",
    "SCL": "Santa Clara",
    "IVI": "Ivins",
    "WAS": "Washington City",
    "LEE": "Leeds",
    "HAR": "Hurricane",
    "HUR": "Hurricane",
    "LAV": "LaVerkin",
    "TOQ": "Toquerville",
    "VIR": "Virgin",
    "ROC": "Rockville",
    "SPR": "Springdale",
    "APV": "Apple Valley",
    "AEG": "Apple Valley / Greendale",
    "ENT": "Enterprise",
    "NHA": "New Harmony",
    "HIL": "Hildale",
    "SR":  "St. George (Research)",
}

# Columns that are consistent across all years
SITE_COL    = "Municipality           + site #"
DATE_COL    = "Date of trap       pick-up"
SPECIES_COL = "Species"
COUNT_COL   = "# Mosq"


def _normalize_virus(val):
    """Return True=positive, False=negative, None=not tested."""
    if pd.isna(val):
        return None
    v = str(val).strip().upper()
    if v in ("Y", "POS", "POSITIVE"):
        return True
    if v in ("N", "NEG", "NEGATIVE", "-"):
        return False
    return None


def _site_prefix(site_str):
    """Extract uppercase alphabetic prefix from a site code like 'SGE001'."""
    if not isinstance(site_str, str):
        return None
    import re
    m = re.match(r"^([A-Za-z]+)", site_str.strip())
    return m.group(1).upper() if m else None


def _coords(site_str):
    prefix = _site_prefix(site_str)
    if prefix and prefix in AREA_COORDS:
        return AREA_COORDS[prefix]
    return (None, None)


def _find_header_row(source_file, sheet_name: str) -> int:
    """
    Auto-detect which row contains the real column headers by scanning for
    'Municipality' (present in all years' header rows).
    Returns the 0-indexed row number to pass as pandas header=.
    """
    probe = pd.read_excel(source_file, sheet_name=sheet_name, header=None, nrows=10)
    for i, row in probe.iterrows():
        if row.astype(str).str.contains("Municipality", case=False).any():
            return i
    return 0  # fallback


def load_trap_data(use_cache: bool = True) -> pd.DataFrame:
    """
    Returns a cleaned DataFrame with columns:
        site, date, year, species, count, wnv, wee, sle, area, lat, lon
    """
    if use_cache and CACHE_PATH.exists():
        return pd.read_csv(CACHE_PATH, parse_dates=["date"])

    print("Loading trap data from source Excel (this takes ~60-90s)...")
    frames = []

    for year in YEAR_SHEETS:
        header_row = _find_header_row(SOURCE_FILE, year)
        raw = pd.read_excel(SOURCE_FILE, sheet_name=year, header=header_row)
        raw.columns = raw.columns.str.strip()

        # Drop entirely empty rows (fixes 2020's 1,048,576-row inflation)
        raw = raw.dropna(how="all").reset_index(drop=True)

        # Skip if core columns are missing
        if SITE_COL not in raw.columns or DATE_COL not in raw.columns:
            print(f"  {year}: skipped — missing core columns")
            continue

        out = pd.DataFrame()
        out["site"]    = raw[SITE_COL].astype(str).str.strip()
        out["date"]    = pd.to_datetime(raw[DATE_COL], errors="coerce")
        out["species"] = raw.get(SPECIES_COL, pd.Series([""] * len(raw))).astype(str).str.strip()
        out["count"]   = pd.to_numeric(raw.get(COUNT_COL, pd.Series(dtype=float)),
                                        errors="coerce").fillna(0)
        out["year"]    = int(year)

        # Virus results differ by era
        if int(year) < 2020:
            out["wnv"] = raw.get("WNV",  pd.Series(dtype=str)).apply(_normalize_virus)
            out["wee"] = raw.get("WEE",  pd.Series(dtype=str)).apply(_normalize_virus)
            out["sle"] = raw.get("SLE",  pd.Series(dtype=str)).apply(_normalize_virus)
        else:
            out["wnv"] = raw.get("Results WNV", pd.Series(dtype=str)).apply(_normalize_virus)
            out["wee"] = raw.get("Results WEE", pd.Series(dtype=str)).apply(_normalize_virus)
            out["sle"] = raw.get("Results SLE", pd.Series(dtype=str)).apply(_normalize_virus)

        frames.append(out)
        print(f"  {year}: {len(out):,} rows loaded")

    df = pd.concat(frames, ignore_index=True)

    # Drop rows with no usable data
    df = df[df["date"].notna()]
    df = df[df["count"] > 0]
    df = df[~df["site"].str.lower().isin(["nan", "", "none"])]
    df = df[df["site"].str.len() > 1]

    # Tighten date range — a few 2016-sheet entries have dates back to 2010
    df = df[df["date"].dt.year >= 2014]

    # Area prefix and coordinates
    df["area"] = df["site"].apply(_site_prefix)
    df["lat"]  = df["site"].apply(lambda s: _coords(s)[0])
    df["lon"]  = df["site"].apply(lambda s: _coords(s)[1])

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE_PATH, index=False)
    print(f"\nSaved {len(df):,} records → {CACHE_PATH}")
    return df


def site_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate trap data by site for GIS map display.
    Returns one row per site with totals, WNV/SLE status, dominant species, active years.
    """
    def top_species(x):
        s = x[~x.isin(["-", "_", "nan", ""])].value_counts()
        return s.index[0] if len(s) > 0 else "Unknown"

    agg = (
        df.groupby(["site", "area", "lat", "lon"])
        .agg(
            total_mosquitoes = ("count", "sum"),
            trap_events      = ("count", "count"),
            wnv_positives    = ("wnv",   lambda x: x.eq(True).sum()),
            wee_positives    = ("wee",   lambda x: x.eq(True).sum()),
            sle_positives    = ("sle",   lambda x: x.eq(True).sum()),
            top_species      = ("species", top_species),
            last_active      = ("date",  "max"),
            first_active     = ("date",  "min"),
            years_active     = ("year",  lambda x: x.nunique()),
        )
        .reset_index()
    )
    agg["any_positive"] = (
        agg["wnv_positives"] + agg["wee_positives"] + agg["sle_positives"]
    ) > 0
    return agg.sort_values("total_mosquitoes", ascending=False)


if __name__ == "__main__":
    df = load_trap_data(use_cache=False)

    print(f"\n{'='*55}")
    print(f"Total records : {len(df):,}")
    print(f"Date range    : {df['date'].min().date()} → {df['date'].max().date()}")

    print("\nMosquito totals by year:")
    print(df.groupby("year")["count"].sum().to_string())

    print("\nTop 10 species by total count:")
    sp = df.groupby("species")["count"].sum().sort_values(ascending=False).head(10)
    print(sp.to_string())

    print("\nWNV positives by year:")
    wnv = df[df["wnv"] == True].groupby("year").size()
    print(wnv.to_string() if len(wnv) else "  None found")

    print("\nSLE positives by year:")
    sle = df[df["sle"] == True].groupby("year").size()
    print(sle.to_string() if len(sle) else "  None found")

    summary = site_summary(df)
    print(f"\nTop 10 sites by total catch:")
    print(summary[["site","area","total_mosquitoes","wnv_positives","sle_positives","top_species"]].head(10).to_string())
