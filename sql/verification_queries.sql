-- 1. Total stored records
SELECT COUNT(*) AS stored_records FROM toyota_listings;

-- 2. Primary key uniqueness (must return 0 duplicated ids)
SELECT COUNT(*) AS duplicated_listing_ids FROM (SELECT listing_id FROM toyota_listings GROUP BY listing_id HAVING COUNT(*) > 1);

-- 3. Listings by pricing status
SELECT pricing_status, COUNT(*) AS n, ROUND(AVG(price_difference_pct), 2) AS avg_pct FROM toyota_listings GROUP BY pricing_status ORDER BY pricing_status;

-- 4. Top 5 models by number of listings
SELECT model, COUNT(*) AS n, ROUND(AVG(price), 0) AS avg_price FROM toyota_listings GROUP BY model ORDER BY n DESC LIMIT 5;

-- 5. Invalid values check (must return 0)
SELECT COUNT(*) AS rows_with_nonpositive_price FROM toyota_listings WHERE price <= 0 OR fair_market_price <= 0;

-- 6. Test records must not be stored (must return 0)
SELECT COUNT(*) AS test_records_in_db FROM toyota_listings WHERE listing_id LIKE 'TEST-%';
