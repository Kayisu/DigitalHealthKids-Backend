import os
import re
import sys
from typing import Optional

import glob
import pandas as pd
import kagglehub

# Ensure project root is on path for shared category helpers
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from app.services.category_constants import canonicalize_category_key

# Config
TOP_N = 10000
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../assets/app_data_kaggle.csv")


def _parse_installs(value: str) -> Optional[int]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value)
    s = s.replace(",", "").replace("+", "").strip()
    if not s.isdigit():
        match = re.findall(r"\d+", s)
        if not match:
            return None
        s = match[0]
    try:
        return int(s)
    except Exception:
        return None


def build_catalog():
    print("Downloading kaggle dataset...")
    path = kagglehub.dataset_download("gauthamp10/google-playstore-apps")
    print(f"Dataset path: {path}")

    # CSV adını esnek bul (bazı sürümlerde farklı olabilir)
    candidates = [
        os.path.join(path, "googleplaystore.csv"),
        os.path.join(path, "google-playstore.csv"),
    ]
    if not any(os.path.exists(c) for c in candidates):
        globbed = glob.glob(os.path.join(path, "*.csv"))
        if globbed:
            csv_path = globbed[0]
            print(f"CSV auto-detected: {csv_path}")
        else:
            raise FileNotFoundError(f"CSV not found in {path}; files: {os.listdir(path)}")
    else:
        csv_path = next(c for c in candidates if os.path.exists(c))

    df = pd.read_csv(csv_path)

    # Expected columns: App Id, App Name, Category, Rating, Installs, Free
    required_cols = ["App Id", "App Name", "Category", "Rating", "Installs", "Free"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns: {missing}")

    df["installs_int"] = df["Installs"].apply(_parse_installs)
    df = df.dropna(subset=["App Id", "App Name", "Category", "installs_int"])

    # Keep top N by installs
    df = df.sort_values(by="installs_int", ascending=False).head(TOP_N)

    # Normalize
    df["package_name"] = df["App Id"].str.strip()
    df["app_name"] = df["App Name"].str.strip()
    df["category"] = df["Category"].astype(str).apply(canonicalize_category_key)
    df["rating"] = pd.to_numeric(df["Rating"], errors="coerce")
    df["free"] = df["Free"].astype(bool)
    df["installs"] = df["installs_int"].astype(int)

    out_df = df[["package_name", "app_name", "category", "rating", "installs", "free"]]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    out_df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(out_df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    try:
        build_catalog()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
