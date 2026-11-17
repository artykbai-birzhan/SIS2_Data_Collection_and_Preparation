from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

COLUMNS = [
    "listing_id", "vin", "title", "year", "make", "model", "trim", "condition",
    "body_style", "fuel", "transmission", "drive_type", "price", "fair_market_price",
    "fair_range_low", "fair_range_high", "mileage", "days_on_site", "deal_rating",
    "dealer_name", "city", "state", "zip", "listing_url", "collected_at",
    "estimated_first_seen_at", "price_difference", "price_difference_pct", "pricing_status",
]

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS toyota_listings (
 listing_id TEXT PRIMARY KEY, vin TEXT NOT NULL, title TEXT, year INTEGER NOT NULL,
 make TEXT NOT NULL CHECK(make='Toyota'), model TEXT NOT NULL, trim TEXT, condition TEXT,
 body_style TEXT, fuel TEXT, transmission TEXT, drive_type TEXT,
 price REAL NOT NULL CHECK(price>0), fair_market_price REAL NOT NULL CHECK(fair_market_price>0),
 fair_range_low REAL, fair_range_high REAL, mileage REAL CHECK(mileage>=0),
 days_on_site REAL CHECK(days_on_site>=0), deal_rating TEXT, dealer_name TEXT,
 city TEXT, state TEXT, zip TEXT, listing_url TEXT, collected_at TEXT NOT NULL,
 estimated_first_seen_at TEXT, price_difference REAL NOT NULL,
 price_difference_pct REAL NOT NULL,
 pricing_status TEXT NOT NULL CHECK(pricing_status IN ('below_market','near_market','above_market'))
)
"""


def _value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value.item() if hasattr(value, "item") else value


def load_dataframe(frame: pd.DataFrame, path: Path) -> int:
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing database columns: {sorted(missing)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    placeholders = ",".join("?" for _ in COLUMNS)
    updates = ",".join(f"{c}=excluded.{c}" for c in COLUMNS if c != "listing_id")
    sql = (
        f"INSERT INTO toyota_listings ({','.join(COLUMNS)}) VALUES ({placeholders}) "
        f"ON CONFLICT(listing_id) DO UPDATE SET {updates}"
    )
    rows = [tuple(_value(v) for v in row) for row in frame[COLUMNS].itertuples(index=False, name=None)]
    with sqlite3.connect(path) as connection:
        connection.execute(CREATE_SQL)
        connection.executemany(sql, rows)
        connection.commit()
        return int(connection.execute("SELECT COUNT(*) FROM toyota_listings").fetchone()[0])


def database_digest(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT * FROM toyota_listings ORDER BY listing_id").fetchall()
    return hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest()


def verification_queries(path: Path) -> dict[str, Any]:
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        count = connection.execute("SELECT COUNT(*) n FROM toyota_listings").fetchone()["n"]
        statuses = connection.execute(
            "SELECT pricing_status, COUNT(*) n, ROUND(AVG(price_difference_pct),2) avg_pct "
            "FROM toyota_listings GROUP BY pricing_status ORDER BY pricing_status"
        ).fetchall()
    return {"stored_records": count, "pricing_status_summary": [dict(r) for r in statuses]}


def run_sql_file(sql_path: Path, db_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Run each SELECT statement in a .sql file and return the rows keyed by its title comment."""
    results: dict[str, list[dict[str, Any]]] = {}
    text = sql_path.read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        for block in text.split(";"):
            lines = [ln for ln in block.strip().splitlines() if ln.strip()]
            if not lines:
                continue
            title = lines[0].lstrip("- ").strip() if lines[0].startswith("--") else f"query_{len(results) + 1}"
            statement = "\n".join(ln for ln in lines if not ln.startswith("--"))
            if statement:
                results[title] = [dict(r) for r in connection.execute(statement).fetchall()]
    return results
