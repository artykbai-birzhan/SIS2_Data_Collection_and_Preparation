import pandas as pd
import pytest


@pytest.fixture
def valid_frame() -> pd.DataFrame:
    rows = []
    values = [
        ("Camry", 25000., 27000., "CA"),
        ("Camry", 27500., 27000., "CA"),
        ("Rav4", 36500., 35000., "TX"),
        ("Rav4", 35100., 35000., "TX"),
    ]
    for i, (model, price, fair, state) in enumerate(values, 1):
        rows.append({
            "listing_id": f"listing-{i}", "vin": f"1HGCM82633A{i:06d}",
            "title": f"2025 Toyota {model}", "year": 2025, "make": "Toyota",
            "model": model, "trim": "LE", "condition": "USED", "body_style": "SUV",
            "fuel": "Gasoline", "transmission": "Automatic", "drive_type": "FWD",
            "price": price, "fair_market_price": fair, "fair_range_low": fair-2000,
            "fair_range_high": fair+2000, "mileage": float(i*1000), "days_on_site": 10.,
            "deal_rating": "Good", "dealer_name": "Example Dealer", "city": "Austin",
            "state": state, "zip": "78701", "listing_url": f"https://example.com/{i}",
            "collected_at": "2026-11-17T10:00:00+00:00",
            "estimated_first_seen_at": "2026-11-07T10:00:00+00:00",
        })
    return pd.DataFrame(rows)

