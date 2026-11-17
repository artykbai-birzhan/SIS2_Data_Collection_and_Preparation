from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.analysis import create_analysis
from src.api_client import collect_to_file
from src.cleaner import clean_and_transform, demonstrate_duplicate_removal
from src.config import Settings
from src.consumer import consume_records
from src.io_utils import read_jsonl, write_json
from src.loader import database_digest, load_dataframe, run_sql_file, verification_queries
from src.producer import publish_records
from src.validator import run_validation


def process(settings: Settings, collected=None, published=None, consumed=None) -> dict:
    validation = run_validation(settings.consumed_path, settings.audit_path.parent)
    stream_counts_path = settings.audit_path.parent / "stream_counts.json"
    saved = json.loads(stream_counts_path.read_text()) if stream_counts_path.exists() else {}
    if collected is None:
        collected = len(read_jsonl(settings.raw_path))
    if published is None:
        published = saved.get("published")
    cleaning = clean_and_transform(validation.valid)
    cleaning.cleaned.to_csv(settings.processed_path, index=False)
    cleaning.model_summary.to_csv(settings.processed_path.parent / "model_summary.csv", index=False)
    cleaning.price_pivot.to_csv(settings.processed_path.parent / "pricing_status_pivot.csv", index=False)

    cleaning.missing_report.to_csv(settings.audit_path.parent / "missing_values_report.csv", index=False)
    first_count = load_dataframe(cleaning.cleaned, settings.sqlite_path)
    first_digest = database_digest(settings.sqlite_path)
    second_count = load_dataframe(cleaning.cleaned, settings.sqlite_path)
    second_digest = database_digest(settings.sqlite_path)
    if first_count != second_count or first_digest != second_digest:
        raise AssertionError("SQLite idempotency test failed")
    eda = create_analysis(cleaning.cleaned, settings.figures_dir)
    audit = {
        "collected_api_records": collected,
        "published_kafka_messages": published,
        "consumed_kafka_messages": consumed or len(read_jsonl(settings.consumed_path)),
        "valid_records": len(validation.valid),
        "invalid_records": len(validation.invalid),
        **cleaning.diagnostics,
        "sqlite_records_after_first_load": first_count,
        "sqlite_records_after_second_load": second_count,
        "sqlite_digest_unchanged": first_digest == second_digest,
        "deliberately_invalid_test_records_detected": validation.test_records_detected,
        **demonstrate_duplicate_removal(cleaning.cleaned),
        "missing_values": {
            str(r.column): int(r.missing_count) for r in cleaning.missing_report.itertuples()
        },
        "eda": eda,
        "database_verification": verification_queries(settings.sqlite_path),
        "sql_verification_file": run_sql_file(Path(__file__).resolve().parent / "sql" / "verification_queries.sql", settings.sqlite_path),
    }
    write_json(settings.audit_path, audit)
    return audit


def stream(settings: Settings, run_id: str) -> tuple[int, int]:
    expected = len(read_jsonl(settings.raw_path))
    published = publish_records(settings, run_id=run_id)
    consumed = consume_records(
        settings, expected, group_id=f"{settings.kafka_group_prefix}-{run_id}", run_id=run_id
    )
    write_json(settings.audit_path.parent / "stream_counts.json", {"published": published, "consumed": consumed})
    return published, consumed


def main() -> None:
    parser = argparse.ArgumentParser(description="Toyota API.SH price-analysis pipeline")
    parser.add_argument("command", choices=("collect", "stream", "process", "all"))
    args = parser.parse_args()
    settings = Settings.from_env(require_api_key=args.command in {"collect", "all"})
    settings.create_directories()
    run_id = str(int(time.time()))
    if args.command == "collect":
        result = {"collected_api_records": collect_to_file(settings)}
    elif args.command == "stream":
        published, consumed = stream(settings, run_id)
        result = {"published": published, "consumed": consumed}
    elif args.command == "process":
        result = process(settings)
    else:
        collected = collect_to_file(settings)
        published, consumed = stream(settings, run_id)
        result = process(settings, collected, published, consumed)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

