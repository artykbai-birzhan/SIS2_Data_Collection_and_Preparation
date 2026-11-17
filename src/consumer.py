from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from confluent_kafka import Consumer, KafkaError, KafkaException

from src.config import Settings
from src.io_utils import write_jsonl


def consume_records(
    settings: Settings,
    expected_count: int,
    output_path: Path | None = None,
    group_id: str | None = None,
    run_id: str = "manual",
) -> int:
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": group_id or f"{settings.kafka_group_prefix}-{int(time.time())}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    records: list[dict] = []
    last_activity = time.monotonic()
    consumer.subscribe([settings.kafka_topic])
    try:
        while len(records) < expected_count:
            message = consumer.poll(1.0)
            if message is None:
                if time.monotonic() - last_activity >= settings.kafka_idle_timeout_seconds:
                    raise TimeoutError(
                        f"Kafka idle timeout after {len(records)}/{expected_count} messages"
                    )
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(message.error())
            last_activity = time.monotonic()
            headers = dict(message.headers() or [])
            message_run_id = headers.get("pipeline_run_id", b"")
            if isinstance(message_run_id, bytes):
                message_run_id = message_run_id.decode()
            if message_run_id != run_id:
                continue
            value = json.loads(message.value().decode())
            if not isinstance(value, dict):
                raise ValueError("Kafka message is not a JSON object")
            records.append(value)
        consumer.commit(asynchronous=False)
    finally:
        consumer.close()
    return write_jsonl(output_path or settings.consumed_path, records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Consume Toyota listings from Kafka")
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--group-id", default=None)
    parser.add_argument("--run-id", default="manual")
    args = parser.parse_args()
    settings = Settings.from_env()
    count = consume_records(
        settings, args.expected_count, args.output, args.group_id, args.run_id
    )
    print(f"consumed_messages={count}")


if __name__ == "__main__":
    main()

