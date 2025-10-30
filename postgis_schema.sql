-- postgis_schema.sql
-- This script runs automatically when the PostgreSQL container starts 
-- because it is mounted to the /docker-entrypoint-initdb.d/ directory.

-- 1. Enable the PostGIS extension.
-- The IF NOT EXISTS clause prevents errors if the script is run multiple times.
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Create a GIST Spatial Index on the 'trucks' location column.
-- This is critical for performance (speeding up ST_DWithin or similar geospatial functions).
-- The index will only be created if the 'trucks' table already exists.
-- NOTE: We use CREATE INDEX IF NOT EXISTS to prevent errors during rebuilds.
-- The GIST access method is the standard and most efficient for spatial data.
CREATE INDEX IF NOT EXISTS idx_trucks_location 
  ON public.trucks 
  USING GIST (location);

-- 3. Run VACUUM ANALYZE (Recommended for production readiness)
-- This updates database statistics, helping the query planner use the new index effectively.
-- It's run against the table where the index was created.
-- VACUUM ANALYZE public.trucks;

-- 3. Run ANALYZE to update statistics.
ANALYZE public.trucks;
