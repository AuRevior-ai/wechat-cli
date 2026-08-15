CREATE TABLE admin_principals (
  id TEXT PRIMARY KEY,
  identity TEXT NOT NULL UNIQUE,
  display_name TEXT,
  scopes_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
  created_at TEXT NOT NULL,
  revoked_at TEXT
);

CREATE TABLE admin_login_codes (
  id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL REFERENCES admin_principals(id),
  challenge_digest TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_admin_login_codes_expiry
  ON admin_login_codes(expires_at);

CREATE TABLE admin_sessions (
  id TEXT PRIMARY KEY,
  token_id TEXT NOT NULL UNIQUE,
  token_digest TEXT NOT NULL,
  principal_id TEXT NOT NULL REFERENCES admin_principals(id),
  scopes_json TEXT NOT NULL,
  authenticated_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
  created_at TEXT NOT NULL,
  last_used_at TEXT,
  revoked_at TEXT
);

CREATE INDEX idx_admin_sessions_principal_status
  ON admin_sessions(principal_id, status, expires_at);
CREATE INDEX idx_admin_sessions_expiry
  ON admin_sessions(expires_at);
