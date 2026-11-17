from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from confluent_kafka import KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from src.config import Settings
from src.io_utils import read_jsonl

LOGGER = logging.getLogger(__name__)


def ensure_topic(bootstrap_servers: str, topic: str) -> None:
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    if topic in admin.list_topics(timeout=10).topics:
        return
    future = admin.create_topics([NewTopic(topic, 1, 1)])[topic]
    try:
        future.result(timeout=15)
    except KafkaException as exc:
        if "TOPIC_ALREADY_EXISTS" not in str(exc):
            raise


def publish_records(
    settings: Settings, input_path: Path | None = None, run_id: str = "manual"
) -> int:
    records = read_jsonl(input_path or settings.raw_path)
    if len(records) < 200:
        raise ValueError(f"Expected at least 200 records, found {len(records)}")
    ensure_topic(settings.kafka_bootstrap_servers, settings.kafka_topic)
    errors: list[str] = []

    def delivered(error, message) -> None:  # type: ignore[no-untyped-def]
        if error is not None:
            errors.append(str(error))

    producer = Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "client.id": "toyota-price-producer",
            "enable.idempotence": True,
            "acks": "all",
        }
    )
    for index, record in enumerate(records):
        listing = record.get("listing", {})
        key = str(listing.get("id") or listing.get("vin") or index)
        while True:
            try:
                producer.produce(
                    settings.kafka_topic,
                    key=key.encode(),
                    value=json.dumps(record, ensure_ascii=False).encode(),
                    headers=[("pipeline_run_id", run_id)],
                    on_delivery=delivered,
                )
                producer.poll(0)
                break
            except BufferError:
                producer.poll(1)
    undelivered = producer.flush(30)
    if undelivered or errors:
        raise RuntimeError(f"Kafka delivery failed: {undelivered=}, errors={errors[:3]}")
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish Toyota listings to Kafka")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--run-id", default="manual")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(f"published_messages={publish_records(Settings.from_env(), args.input, args.run_id)}")


if __name__ == "__main__":
    main()

