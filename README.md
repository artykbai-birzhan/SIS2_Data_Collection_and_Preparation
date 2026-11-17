# Toyota Car Price Analysis

**Topic:** Comparing Market Listing Prices and KBB Fair Market Prices  
**API:** API.SH Autotrader Search

Connected SIS 2 pipeline:

```text
API.SH -> raw JSONL -> Kafka Producer -> Kafka Topic -> Kafka Consumer
       -> Pandera -> pandas/NumPy -> SQLite -> EDA and figures
```

API.SH currently provides 1,000 free credits per month without requiring a card. Its terms explicitly allow storing factual response fields such as prices and identifiers. Do not store or redistribute copyrighted descriptions or images; this project selects factual listing fields only.

## Setup

Requirements: Python 3.11+, Docker Desktop, and a free API.SH key from <https://app.api.sh/signup>.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and replace `APISH_KEY=replace_me` with your key. Do not commit `.env`.

Start a real Kafka broker:

```bash
docker compose up -d
docker compose ps
```

Run tests and the complete pipeline:

```bash
pytest -q
python main.py all
```

The collector requests Toyota listings from `GET https://api.api.sh/autotrader/v1/search`, using the `x-api-key` header. It paginates until it has at least 250 unique listings containing both `price` and `kbb_fair_price`. Increase `MAX_API_PAGES` or change ZIP/radius if fewer than 200 comparable records are available.

## Separate stages

```bash
python main.py collect
python main.py stream
python main.py process
```

The producer and consumer are independent scripts:

```bash
python -m src.producer --run-id demo-1
python -m src.consumer --expected-count 250 --run-id demo-1 --group-id demo-1
```

Use the actual line count from `wc -l data/raw/toyota_listings.jsonl` as `--expected-count`.

## Validation

Pandera runs before cleaning and checks at least:

1. unique nonempty listing ID;
2. valid 17-character VIN;
3. plausible model year;
4. Toyota make;
5. nonempty model;
6. positive listing price;
7. positive fair-market price;
8. nonnegative mileage and days on site;
9. parseable collection timestamp.

Invalid rows are quarantined. Three tagged test records demonstrate wrong price, make, and VIN detection.

## Transformations and analysis

```text
price_difference = price - fair_market_price
price_difference_pct = price_difference / fair_market_price * 100
```

Using a 3% tolerance, listings are classified as `below_market`, `near_market`, or `above_market`. The pipeline also performs text standardization, datetime conversion, duplicate removal, NumPy vectorized arithmetic, multi-condition filtering, GroupBy aggregation, and a pivot-table reshape.

Generated charts:

1. listing price vs KBB fair price;
2. median percentage difference by Toyota model;
3. market-position category counts.

## Outputs

| Path | Contents |
|---|---|
| `data/raw/toyota_listings.jsonl` | Original factual source values wrapped with collection metadata; descriptions/images are excluded |
| `data/raw/consumed_listings.jsonl` | Messages actually received from Kafka |
| `data/processed/toyota_prices.csv` | Validated and transformed records |
| `data/processed/model_summary.csv` | GroupBy output |
| `data/processed/pricing_status_pivot.csv` | Pivot-table output |
| `data/toyota_prices.db` | SQLite database |
| `artifacts/pipeline_audit.json` | All pipeline counts and verification results |
| `artifacts/*validation*.csv` | Validation evidence |
| `figures/*.png` | Three EDA charts |

SQLite uses `listing_id` as its primary key and `ON CONFLICT DO UPDATE`. The same dataframe is loaded twice; both row count and SHA-256 database-content digest must remain unchanged.

## Troubleshooting

- `401/403`: check `APISH_KEY`.
- Fewer than 200 records: increase `MAX_API_PAGES`, ZIP/radius, or `TARGET_RECORDS`.
- `docker: command not found`: install and open Docker Desktop.
- Kafka timeout: ensure Kafka is healthy and the producer/consumer use the same `run-id`.
- Never put the API key, `.env`, copyrighted descriptions, or listing images in GitHub.
