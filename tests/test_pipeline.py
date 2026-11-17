from pathlib import Path

import pandas as pd

from src.analysis import create_analysis
from src.cleaner import clean_and_transform, demonstrate_duplicate_removal, missing_value_report
from src.loader import database_digest, load_dataframe
from src.normalizer import normalize_listing
from src.validator import deliberately_invalid_records, validate_dataframe


def test_normalizer() -> None:
    value = normalize_listing({
        "_collection": {"collected_at": "2026-11-17T10:00:00Z"},
        "listing": {"id": 1, "vin": "1HGCM82633A123456", "year": 2025,
                    "make": "Toyota", "model": "Camry", "price": 25000,
                    "kbb_fair_price": 27000, "days_on_site": 5},
    })
    assert value["fair_market_price"] == 27000
    assert value["estimated_first_seen_at"].startswith("2026-11-12")


def test_validation_and_deliberate_errors(valid_frame: pd.DataFrame) -> None:
    result = validate_dataframe(valid_frame)
    assert len(result.valid) == 4
    tests = validate_dataframe(deliberately_invalid_records(result.valid))
    assert len(tests.invalid) == 3


def test_cleaning_features(valid_frame: pd.DataFrame) -> None:
    clean = clean_and_transform(valid_frame).cleaned
    assert {"below_market", "near_market", "above_market"} == set(clean["pricing_status"])
    assert round(clean.query("listing_id == 'listing-1'").iloc[0]["price_difference_pct"], 2) == -7.41


def test_idempotent_load(tmp_path: Path, valid_frame: pd.DataFrame) -> None:
    clean = clean_and_transform(valid_frame).cleaned
    database = tmp_path / "test.db"
    assert load_dataframe(clean, database) == 4
    digest = database_digest(database)
    assert load_dataframe(clean, database) == 4
    assert database_digest(database) == digest


def test_figures(tmp_path: Path, valid_frame: pd.DataFrame) -> None:
    clean = clean_and_transform(valid_frame).cleaned
    assert create_analysis(clean, tmp_path)["records_analyzed"] == 4
    assert len(list(tmp_path.glob("*.png"))) == 3


def test_missing_report_and_duplicates(valid_frame: pd.DataFrame) -> None:
    frame = valid_frame.copy()
    frame.loc[0, "mileage"] = None
    frame.loc[1, "trim"] = None
    report = missing_value_report(frame)
    assert set(report["column"]) == {"mileage", "trim"}
    clean = clean_and_transform(frame).cleaned
    assert (clean["trim"] == "Unknown").sum() == 1
    assert clean["mileage"].isna().sum() == 1
    assert demonstrate_duplicate_removal(valid_frame, copies=2)["duplicate_demo_rows_removed"] == 2


def test_model_name_fix(valid_frame: pd.DataFrame) -> None:
    frame = valid_frame.copy()
    frame["model"] = ["rav4", "rav4", "Camry", "Camry"]
    assert "RAV4" in set(clean_and_transform(frame).cleaned["model"])
