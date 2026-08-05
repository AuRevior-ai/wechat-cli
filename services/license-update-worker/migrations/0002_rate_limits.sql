CREATE TABLE rate_limit_windows (
  key TEXT PRIMARY KEY,
  window_start TEXT NOT NULL,
  count INTEGER NOT NULL CHECK (count >= 1),
  expires_at TEXT NOT NULL
);

CREATE INDEX idx_rate_limit_expiry ON rate_limit_windows(expires_at);
