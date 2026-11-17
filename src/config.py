from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_url: str
    zip_code: str
    radius: int
    target_records: int
    max_api_pages: int
    kafka_bootstrap_servers: str
    kafka_topic: str
    kafka_group_prefix: str
    kafka_idle_timeout_seconds: int
    sqlite_path: Path
    raw_path: Path = Path("data/raw/toyota_listings.jsonl")
    consumed_path: Path = Path("data/raw/consumed_listings.jsonl")
    processed_path: Path = Path("data/processed/toyota_prices.csv")
    audit_path: Path = Path("artifacts/pipeline_audit.json")
    figures_dir: Path = Path("figures")

    @classmethod
    def from_env(cls, require_api_key: bool = False) -> "Settings":
        load_dotenv()
        key = os.getenv("APISH_KEY", "").strip()
        if require_api_key and (not key or key == "replace_me"):
            raise RuntimeError(
                "APISH_KEY is missing. Copy .env.example to .env and add your API.SH key."
            )
        return cls(
            api_key=key,
            api_url=os.getenv(
                "APISH_BASE_URL", "https://api.api.sh/autotrader/v1/search"
            ),
            zip_code=os.getenv("APISH_ZIP", "78701"),
            radius=int(os.getenv("APISH_RADIUS", "100")),
            target_records=int(os.getenv("TARGET_RECORDS", "250")),
            max_api_pages=int(os.getenv("MAX_API_PAGES", "40")),
            kafka_bootstrap_servers=os.getenv(
                "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
            ),
            kafka_topic=os.getenv("KAFKA_TOPIC", "toyota-price-listings"),
            kafka_group_prefix=os.getenv(
                "KAFKA_GROUP_PREFIX", "toyota-price-analysis"
            ),
            kafka_idle_timeout_seconds=int(
                os.getenv("KAFKA_IDLE_TIMEOUT_SECONDS", "15")
            ),
            sqlite_path=Path(os.getenv("SQLITE_PATH", "data/toyota_prices.db")),
        )

    def create_directories(self) -> None:
        for path in (
            self.raw_path.parent,
            self.processed_path.parent,
            self.sqlite_path.parent,
            self.audit_path.parent,
            self.figures_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

