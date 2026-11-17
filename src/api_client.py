from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import Settings
from src.io_utils import write_jsonl

LOGGER = logging.getLogger(__name__)


def _factual_projection(listing: dict[str, Any]) -> dict[str, Any]:
    """Keep factual analysis fields and omit descriptions, photos, and reviews."""
    fields = (
        "id", "url", "title", "vin", "stock_number", "year", "make", "model",
        "trim", "condition", "price", "kbb_fair_price", "mileage", "body_style",
        "drive_type", "engine", "fuel", "transmission", "days_on_site",
        "new_listing", "reduced_price", "deal_rating",
    )
    projected = {field: listing.get(field) for field in fields}
    fair_range = listing.get("kbb_fair_range")
    projected["kbb_fair_range"] = dict(fair_range) if isinstance(fair_range, dict) else None
    dealer = listing.get("dealer")
    if isinstance(dealer, dict):
        projected["dealer"] = {
            key: dealer.get(key)
            for key in ("id", "name", "city", "state", "zip", "latitude", "longitude")
        }
    else:
        projected["dealer"] = None
    return projected


class ApiShClient:
    def __init__(self, settings: Settings, timeout_seconds: int = 120) -> None:
        if not settings.api_key:
            raise ValueError("An API.SH key is required")
        self.settings = settings
        self.timeout_seconds = timeout_seconds
        retry = Retry(
            total=4,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def fetch_toyota_listings(self, target_records: int | None = None) -> list[dict[str, Any]]:
        target = target_records or self.settings.target_records
        if target < 200:
            raise ValueError("The assignment requires at least 200 records")

        collected: list[dict[str, Any]] = []
        seen: set[str] = set()
        page = 1

        while len(collected) < target and page <= self.settings.max_api_pages:
            params = {
                "make": "Toyota",
                "zip": self.settings.zip_code,
                "radius": str(self.settings.radius),
                "page": str(page),
            }
            LOGGER.info("Requesting API.SH Autotrader page %s", page)
            response = self.session.get(
                self.settings.api_url,
                params=params,
                headers={"x-api-key": self.settings.api_key, "Accept": "application/json"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            listings = payload.get("listings", [])
            if not isinstance(listings, list):
                raise ValueError("Unexpected API.SH response: listings is not a list")
            if not listings:
                break

            collected_at = datetime.now(timezone.utc).isoformat()
            for listing in listings:
                if not isinstance(listing, dict):
                    continue
                identity = str(listing.get("id") or listing.get("vin") or "")
                if not identity or identity in seen:
                    continue
                # The study needs both prices. Source values are preserved before
                # cleaning, while copyrighted descriptions and images are excluded.
                if listing.get("price") in (None, "") or listing.get("kbb_fair_price") in (
                    None,
                    "",
                ):
                    continue
                seen.add(identity)
                collected.append(
                    {
                        "_collection": {
                            "collected_at": collected_at,
                            "api": "API.SH Autotrader search",
                            "page": page,
                        },
                        "listing": _factual_projection(listing),
                    }
                )
                if len(collected) >= target:
                    break

            LOGGER.info("Comparable unique listings collected: %s", len(collected))
            next_page = payload.get("next_page")
            if next_page in (None, False, ""):
                break
            try:
                next_value = int(next_page)
            except (TypeError, ValueError):
                next_value = page + 1
            if next_value <= page:
                break
            page = next_value
            time.sleep(0.15)

        if len(collected) < 200:
            raise RuntimeError(
                f"Only {len(collected)} comparable Toyota records were collected; "
                "at least 200 with price and kbb_fair_price are required. Increase "
                "MAX_API_PAGES or change ZIP/radius."
            )
        return collected


def collect_to_file(settings: Settings, output_path: Path | None = None) -> int:
    records = ApiShClient(settings).fetch_toyota_listings()
    count = write_jsonl(output_path or settings.raw_path, records)
    LOGGER.info("Preserved %s API listing envelopes", count)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Toyota listings from API.SH")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env(require_api_key=True)
    settings.create_directories()
    print(f"collected_records={collect_to_file(settings, args.output)}")


if __name__ == "__main__":
    main()
