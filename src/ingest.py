"""
Load and normalize building + grading permit data into a unified DataFrame.
"""
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "Downloads" / "SWMAC Project" / "permits_extracted"
GRADING_FILE = DATA_DIR / "Grading Permits 1.1.15 to 2.24.26.xlsx"
BUILDING_FILE = DATA_DIR / "bld permits 2015-current GRAMA.xlsx"

# Permit types considered high or medium risk for mosquito breeding
HIGH_RISK_TYPES = {
    "Grading/Site Plan (Commercial/Apartments)",
    "Commercial (New Build)",
    "Public",
}
MEDIUM_RISK_TYPES = {
    "Multi-Family (townhome)",
    "Multi-Family (apartment)",
    "Single Family",
}

# These building permit types are mostly interior work — low mosquito risk
LOW_RISK_KEYWORDS = [
    "mechanical", "plumbing", "electrical", "gas line", "reroof",
    "interior", "tenant improvement", "sign", "fence",
]


def _classify_risk(permit_type: str) -> str:
    pt = str(permit_type).strip()
    if pt in HIGH_RISK_TYPES:
        return "HIGH"
    if pt in MEDIUM_RISK_TYPES:
        return "MEDIUM"
    pt_lower = pt.lower()
    if any(kw in pt_lower for kw in LOW_RISK_KEYWORDS):
        return "LOW"
    return "MEDIUM"  # unknown types default to medium


def load_grading_permits() -> pd.DataFrame:
    df = pd.read_excel(GRADING_FILE, header=1, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={
        "Issue Date": "date",
        "Permit #": "permit_id",
        "Permit Type": "permit_type",
        "Project Name": "project_name",
        "Street Address": "address",
        "Parcel Number": "parcel",
    })
    df = df[["date", "permit_id", "permit_type", "project_name", "address", "parcel"]].copy()
    df["source"] = "grading"
    df["risk_class"] = "HIGH"  # all grading permits are high risk
    return df


def load_building_permits() -> pd.DataFrame:
    df = pd.read_excel(BUILDING_FILE, header=0, engine="openpyxl")
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(columns={
        "date": "date",
        "permit #": "permit_id",
        "permit type": "permit_type",
        "project name": "project_name",
        "street address": "address",
        "parcel number": "parcel",
    })
    keep = ["date", "permit_id", "permit_type", "project_name", "address", "parcel"]
    df = df[keep].copy()
    df["source"] = "building"
    df["risk_class"] = df["permit_type"].apply(_classify_risk)
    return df


def load_all_permits() -> pd.DataFrame:
    grading = load_grading_permits()
    building = load_building_permits()
    combined = pd.concat([grading, building], ignore_index=True)

    # Normalize dates
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined = combined.dropna(subset=["date", "address"])
    combined["address"] = combined["address"].astype(str).str.strip()
    combined = combined[combined["address"].str.len() > 3]

    # Drop exact duplicates
    combined = combined.drop_duplicates(subset=["permit_id"])
    combined = combined.sort_values("date", ascending=False).reset_index(drop=True)

    return combined


if __name__ == "__main__":
    df = load_all_permits()
    print(f"Total permits loaded: {len(df)}")
    print(df["risk_class"].value_counts())
    print(df.head(5).to_string())
