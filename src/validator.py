from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from src.io_utils import read_jsonl
from src.normalizer import normalize_records


@dataclass
class ValidationResult:
    valid: pd.DataFrame
    invalid: pd.DataFrame
    errors: pd.DataFrame
    test_records_detected: int = 0


def _parseable_timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).notna()


def build_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "listing_id": pa.Column(str, pa.Check.str_length(min_value=1), unique=True),
            "vin": pa.Column(str, pa.Check.str_matches(r"^[A-HJ-NPR-Z0-9]{17}$")),
            "year": pa.Column(int, pa.Check.in_range(1980, datetime.now().year + 2)),
            "make": pa.Column(str, pa.Check.isin(["Toyota"])),
            "model": pa.Column(str, pa.Check.str_length(min_value=1)),
            "price": pa.Column(float, pa.Check.gt(0)),
            "fair_market_price": pa.Column(float, pa.Check.gt(0)),
            "mileage": pa.Column(float, pa.Check.ge(0), nullable=True),
            "days_on_site": pa.Column(float, pa.Check.ge(0), nullable=True),
            "collected_at": pa.Column(str, pa.Check(_parseable_timestamp)),
        },
        coerce=True,
        strict=False,
    )


def validate_dataframe(frame: pd.DataFrame) -> ValidationResult:
    candidate = frame.copy().reset_index(drop=True)
    try:
        valid = build_schema().validate(candidate, lazy=True)
        return ValidationResult(valid, candidate.iloc[0:0].copy(), pd.DataFrame())
    except SchemaErrors as exc:
        errors = exc.failure_cases.copy()
        indexes: set[int] = set()
        for value in errors.get("index", pd.Series(dtype=object)).dropna():
            try:
                indexes.add(int(value))
            except (TypeError, ValueError):
                pass
        if not indexes:
            raise ValueError("Validation error could not be assigned to rows") from exc
        invalid = candidate.loc[sorted(indexes)].copy()
        valid = build_schema().validate(candidate.drop(index=sorted(indexes)), lazy=True)
        return ValidationResult(valid.reset_index(drop=True), invalid, errors)


def deliberately_invalid_records(valid: pd.DataFrame) -> pd.DataFrame:
    base = valid.iloc[0].to_dict()
    return pd.DataFrame(
        [
            dict(base, listing_id="TEST-BAD-PRICE", price=-1.0),
            dict(base, listing_id="TEST-BAD-MAKE", make="Honda"),
            dict(base, listing_id="TEST-BAD-VIN", vin="INVALID"),
        ]
    )


def run_validation(input_path: Path, output_dir: Path) -> ValidationResult:
    frame = pd.DataFrame(normalize_records(read_jsonl(input_path)))
    result = validate_dataframe(frame)
    output_dir.mkdir(parents=True, exist_ok=True)
    result.invalid.to_csv(output_dir / "invalid_records.csv", index=False)
    result.errors.to_csv(output_dir / "validation_errors.csv", index=False)
    tests = validate_dataframe(deliberately_invalid_records(result.valid))
    tests.invalid.assign(test_record=True).to_csv(
        output_dir / "deliberately_invalid_records.csv", index=False
    )
    tests.errors.to_csv(output_dir / "deliberately_invalid_errors.csv", index=False)
    if len(tests.invalid) != 3:
        raise AssertionError("Three deliberately invalid records were not detected")
    result.test_records_detected = len(tests.invalid)
    return result

