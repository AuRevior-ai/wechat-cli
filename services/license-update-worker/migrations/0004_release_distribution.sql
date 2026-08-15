ALTER TABLE releases ADD COLUMN distribution_backend TEXT NOT NULL DEFAULT 'github'
  CHECK (distribution_backend IN ('github', 'r2'));
ALTER TABLE releases ADD COLUMN distribution_object_key TEXT;

CREATE INDEX idx_releases_distribution_backend
  ON releases(distribution_backend, channel, enabled, paused, published_at DESC);
