from __future__ import annotations

import os
from pathlib import Path

cache = Path(".cache/matplotlib").resolve()
cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(cache))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def _save(figure: plt.Figure, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def create_analysis(frame: pd.DataFrame, output: Path) -> dict[str, object]:
    if frame.empty:
        raise ValueError("Cannot analyze an empty dataframe")
    output.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    figure, axis = plt.subplots(figsize=(8, 6))
    sns.scatterplot(data=frame, x="fair_market_price", y="price", hue="pricing_status", alpha=.7, ax=axis)
    low = min(frame["fair_market_price"].min(), frame["price"].min())
    high = max(frame["fair_market_price"].max(), frame["price"].max())
    axis.plot([low, high], [low, high], "--", color="black", label="Listing = fair price")
    axis.set(title="Toyota Listing Price vs KBB Fair Market Price", xlabel="KBB fair market price (USD)", ylabel="Listing price (USD)")
    axis.legend(title="Pricing status")
    _save(figure, output / "01_listing_vs_fair_price.png")

    min_listings = 5
    all_stats = frame.groupby("model").agg(
        median_difference_pct=("price_difference_pct", "median"),
        listing_count=("listing_id", "count"),
    )
    stats = all_stats.query("listing_count >= @min_listings").sort_values("median_difference_pct")
    if stats.empty:
        stats = all_stats.sort_values("median_difference_pct")
    stats = stats.reset_index()
    figure, axis = plt.subplots(figsize=(10, max(5, len(stats) * .45)))
    sns.barplot(data=stats, x="median_difference_pct", y="model", color="#4C72B0", ax=axis)
    for position, row in enumerate(stats.itertuples()):
        axis.text(row.median_difference_pct, position, f"  n={row.listing_count}", va="center", fontsize=8)
    axis.axvline(0, color="black", linewidth=1)
    axis.set(
        title=f"Median Difference from Fair Price by Model (models with >= {min_listings} listings)",
        xlabel="Median difference (%)",
        ylabel="Model",
    )
    _save(figure, output / "02_difference_by_model.png")

    figure, axis = plt.subplots(figsize=(8, 5))
    order = ["below_market", "near_market", "above_market"]
    sns.countplot(data=frame, x="pricing_status", order=order, hue="pricing_status", legend=False, ax=axis)
    axis.set(title="Toyota Listings by Market Position", xlabel="Market position (3% tolerance)", ylabel="Listings")
    _save(figure, output / "03_pricing_status.png")

    return {
        "records_analyzed": int(len(frame)),
        "mean_listing_price": round(float(frame["price"].mean()), 2),
        "mean_fair_market_price": round(float(frame["fair_market_price"].mean()), 2),
        "median_difference_pct": round(float(frame["price_difference_pct"].median()), 2),
        "pricing_status_counts": {str(k): int(v) for k, v in frame["pricing_status"].value_counts().items()},
        "model_count": int(frame["model"].nunique()),
    }

