from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class CleaningResult:
    cleaned: pd.DataFrame
    model_summary: pd.DataFrame
    price_pivot: pd.DataFrame
    diagnostics: dict[str, int]
    missing_report: pd.DataFrame


MODEL_FIXES = {"Rav4": "RAV4", "Fj Cruiser": "FJ Cruiser", "Gr86": "GR86", "Gr Corolla": "GR Corolla"}
CATEGORY_COLUMNS = ["trim", "condition", "body_style", "fuel", "transmission", "drive_type"]
NUMERIC_NULLABLE = ["mileage", "days_on_site", "fair_range_low", "fair_range_high"]


def missing_value_report(frame: pd.DataFrame) -> pd.DataFrame:
    """Count and percentage of missing values per column (only columns with gaps)."""
    counts = frame.isna().sum()
    report = pd.DataFrame(
        {"column": counts.index, "missing_count": counts.values,
         "missing_pct": np.round(counts.values / len(frame) * 100.0, 2)}
    )
    return report[report["missing_count"] > 0].reset_index(drop=True)


def demonstrate_duplicate_removal(frame: pd.DataFrame, copies: int = 3) -> dict[str, int]:
    """Add exact copies of real rows and show that the cleaning step removes them."""
    duplicated = pd.concat([frame, frame.head(copies)], ignore_index=True)
    removed = len(duplicated) - len(duplicated.drop_duplicates(subset=["listing_id"], keep="last"))
    return {"duplicate_demo_rows_added": int(copies), "duplicate_demo_rows_removed": int(removed)}


def clean_and_transform(frame: pd.DataFrame, tolerance_pct: float = 3.0) -> CleaningResult:
    if frame.empty:
        raise ValueError("Cannot clean an empty dataframe")
    before = len(frame)
    clean = frame.drop_duplicates(subset=["listing_id"], keep="last").copy()
    for column in (
        "make",
        "model",
        "trim",
        "condition",
        "body_style",
        "fuel",
        "transmission",
        "drive_type",
        "dealer_name",
        "city",
        "state",
    ):
        clean[column] = clean[column].astype("string").str.strip()
    clean["make"] = clean["make"].str.title()
    clean["model"] = clean["model"].str.title()
    clean["state"] = clean["state"].str.upper()
    clean["model"] = clean["model"].replace(MODEL_FIXES)
    missing_report = missing_value_report(clean)
    # Strategy: categorical gaps become an explicit "Unknown"; numeric gaps stay
    # null on purpose (imputing mileage or prices would invent data).
    for column in CATEGORY_COLUMNS:
        clean[column] = clean[column].fillna("Unknown")
    clean["collected_at"] = pd.to_datetime(clean["collected_at"], utc=True)
    clean["estimated_first_seen_at"] = pd.to_datetime(
        clean["estimated_first_seen_at"], errors="coerce", utc=True
    )
    clean["price_difference"] = np.subtract(clean["price"], clean["fair_market_price"])
    clean["price_difference_pct"] = np.divide(
        clean["price_difference"], clean["fair_market_price"]
    ) * 100.0
    tolerance = abs(float(tolerance_pct))
    clean["pricing_status"] = np.select(
        [
            clean["price_difference_pct"] < -tolerance,
            clean["price_difference_pct"] > tolerance,
        ],
        ["below_market", "above_market"],
        default="near_market",
    )
    attractive = clean[
        (clean["pricing_status"] == "below_market")
        & (clean["mileage"].fillna(float("inf")) < 60000)
        & clean["model"].notna()
    ]
    summary = (
        clean.groupby("model", dropna=False)
        .agg(
            listing_count=("listing_id", "count"),
            mean_price=("price", "mean"),
            mean_fair_price=("fair_market_price", "mean"),
            median_difference_pct=("price_difference_pct", "median"),
            median_mileage=("mileage", "median"),
        )
        .sort_values("listing_count", ascending=False)
        .reset_index()
    )
    pivot = pd.pivot_table(
        clean,
        index="model",
        columns="pricing_status",
        values="listing_id",
        aggfunc="count",
        fill_value=0,
    ).reset_index()
    clean = clean.sort_values(["model", "year", "listing_id"]).reset_index(drop=True)
    return CleaningResult(
        clean,
        summary,
        pivot,
        {
            "records_before_cleaning": before,
            "duplicate_records_removed": before - len(clean),
            "records_after_cleaning": len(clean),
            "attractive_below_market_records": len(attractive),
        },
        missing_report,
    )

