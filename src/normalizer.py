from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip()


def normalize_listing(envelope: dict[str, Any]) -> dict[str, Any]:
    listing = envelope.get("listing", envelope)
    metadata = envelope.get("_collection", {})
    if not isinstance(listing, dict):
        listing = {}
    if not isinstance(metadata, dict):
        metadata = {}
    fair_range = listing.get("kbb_fair_range", {})
    if not isinstance(fair_range, dict):
        fair_range = {}
    dealer = listing.get("dealer", {})
    if not isinstance(dealer, dict):
        dealer = {}
    collected_at = _text(metadata.get("collected_at"))
    days_on_site = _number(listing.get("days_on_site"))
    estimated_first_seen_at = None
    if collected_at and days_on_site is not None:
        parsed = pd.to_datetime(collected_at, utc=True, errors="coerce")
        if not pd.isna(parsed):
            estimated_first_seen_at = (parsed - timedelta(days=days_on_site)).isoformat()
    return {
        "listing_id": _text(listing.get("id")),
        "vin": _text(listing.get("vin")),
        "title": _text(listing.get("title")),
        "year": listing.get("year"),
        "make": _text(listing.get("make")),
        "model": _text(listing.get("model")),
        "trim": _text(listing.get("trim")),
        "condition": _text(listing.get("condition")),
        "body_style": _text(listing.get("body_style")),
        "fuel": _text(listing.get("fuel")),
        "transmission": _text(listing.get("transmission")),
        "drive_type": _text(listing.get("drive_type")),
        "price": _number(listing.get("price")),
        "fair_market_price": _number(listing.get("kbb_fair_price")),
        "fair_range_low": _number(fair_range.get("low")),
        "fair_range_high": _number(fair_range.get("high")),
        "mileage": _number(listing.get("mileage")),
        "days_on_site": days_on_site,
        "deal_rating": _text(listing.get("deal_rating")),
        "dealer_name": _text(dealer.get("name")),
        "city": _text(dealer.get("city")),
        "state": _text(dealer.get("state")),
        "zip": _text(dealer.get("zip")),
        "listing_url": _text(listing.get("url")),
        "collected_at": collected_at,
        "estimated_first_seen_at": estimated_first_seen_at,
    }


def normalize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_listing(record) for record in records]
