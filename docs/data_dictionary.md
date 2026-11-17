# Data dictionary

| Field | Type | Meaning |
|---|---|---|
| `listing_id` | text | Autotrader listing identifier; SQLite primary key |
| `vin` | text | 17-character VIN |
| `year`, `make`, `model`, `trim` | mixed | Vehicle identity fields |
| `condition`, `body_style`, `fuel`, `transmission`, `drive_type` | text | Vehicle categories |
| `price` | real | Advertised listing price in USD |
| `fair_market_price` | real | API response `kbb_fair_price` in USD |
| `fair_range_low`, `fair_range_high` | real/null | Fair-price range bounds |
| `mileage` | real/null | Odometer miles |
| `days_on_site` | real/null | Number of days the listing has been visible |
| `deal_rating` | text/null | Source deal classification |
| `dealer_name`, `city`, `state`, `zip` | text/null | Dealer/location facts |
| `listing_url` | text/null | Source listing link |
| `collected_at` | UTC datetime | Pipeline collection time |
| `estimated_first_seen_at` | UTC datetime/null | `collected_at - days_on_site`; approximate, not a source timestamp |
| `price_difference` | real | `price - fair_market_price` |
| `price_difference_pct` | real | Percentage difference from fair price |
| `pricing_status` | category | below, near, or above market using 3% tolerance |

