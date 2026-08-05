PRAGMA foreign_keys = ON;

CREATE TABLE licenses (
  id TEXT PRIMARY KEY,
  key_digest TEXT NOT NULL UNIQUE,
  key_hint TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'suspended', 'revoked')),
  max_devices INTEGER NOT NULL DEFAULT 3 CHECK (max_devices BETWEEN 1 AND 100),
  release_channel TEXT NOT NULL DEFAULT 'stable' CHECK (release_channel IN ('stable', 'beta')),
  revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  suspended_at TEXT,
  revoked_at TEXT,
  created_by_admin_id TEXT
);

CREATE TABLE license_contacts (
  license_id TEXT PRIMARY KEY REFERENCES licenses(id) ON DELETE CASCADE,
  ciphertext BLOB,
  iv BLOB,
  encryption_key_version INTEGER,
  email_lookup_digest TEXT,
  wechat_lookup_digest TEXT,
  other_lookup_digest TEXT,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_license_contacts_email ON license_contacts(email_lookup_digest);
CREATE INDEX idx_license_contacts_wechat ON license_contacts(wechat_lookup_digest);

CREATE TABLE devices (
  id TEXT PRIMARY KEY,
  license_id TEXT NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
  client_install_id_digest TEXT NOT NULL,
  fingerprint_digest TEXT,
  display_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled', 'unbound')),
  token_id TEXT NOT NULL UNIQUE,
  token_secret_digest TEXT NOT NULL,
  token_version INTEGER NOT NULL DEFAULT 1 CHECK (token_version >= 1),
  device_revision INTEGER NOT NULL DEFAULT 1 CHECK (device_revision >= 1),
  first_activated_at TEXT NOT NULL,
  last_validated_at TEXT,
  last_app_version TEXT,
  last_launcher_version TEXT,
  disabled_at TEXT,
  unbound_at TEXT
);

CREATE INDEX idx_devices_license_status ON devices(license_id, status);
CREATE INDEX idx_devices_install_id ON devices(license_id, client_install_id_digest);
CREATE INDEX idx_devices_fingerprint ON devices(license_id, fingerprint_digest);

CREATE TABLE releases (
  id TEXT PRIMARY KEY,
  version TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('stable', 'beta')),
  manifest_content BLOB NOT NULL,
  manifest_signature BLOB NOT NULL,
  manifest_sha256 TEXT NOT NULL,
  package_sha256 TEXT NOT NULL,
  package_size INTEGER NOT NULL CHECK (package_size > 0),
  github_repository TEXT NOT NULL,
  github_release_id TEXT NOT NULL,
  github_asset_id TEXT NOT NULL,
  github_asset_name TEXT NOT NULL,
  rollout_percentage INTEGER NOT NULL DEFAULT 100 CHECK (rollout_percentage BETWEEN 0 AND 100),
  rollout_seed TEXT NOT NULL,
  paused INTEGER NOT NULL DEFAULT 1 CHECK (paused IN (0, 1)),
  enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
  published_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(channel, version)
);

CREATE INDEX idx_releases_available ON releases(channel, enabled, paused, published_at DESC);

CREATE TABLE download_tickets (
  id TEXT PRIMARY KEY,
  ticket_digest TEXT NOT NULL UNIQUE,
  release_id TEXT NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
  license_id TEXT NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
  device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  expected_sha256 TEXT NOT NULL,
  expected_size INTEGER NOT NULL CHECK (expected_size > 0),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_used_at TEXT,
  revoked_at TEXT
);

CREATE INDEX idx_download_tickets_expiry ON download_tickets(expires_at);

CREATE TABLE admin_tokens (
  id TEXT PRIMARY KEY,
  token_id TEXT NOT NULL UNIQUE,
  token_digest TEXT NOT NULL,
  display_name TEXT,
  scopes_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
  created_at TEXT NOT NULL,
  last_used_at TEXT,
  revoked_at TEXT
);

CREATE TABLE audit_events (
  id TEXT PRIMARY KEY,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('admin', 'license', 'device', 'system')),
  actor_id TEXT,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  result TEXT NOT NULL,
  request_id TEXT NOT NULL,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_audit_events_created ON audit_events(created_at DESC);
CREATE INDEX idx_audit_events_target ON audit_events(target_type, target_id, created_at DESC);

CREATE TABLE idempotency_records (
  scope TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_digest TEXT NOT NULL,
  response_status INTEGER NOT NULL,
  response_body TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  PRIMARY KEY(scope, idempotency_key)
);

CREATE INDEX idx_idempotency_expiry ON idempotency_records(expires_at);

CREATE TABLE diagnostic_submissions (
  id TEXT PRIMARY KEY,
  license_id TEXT NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
  device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  object_key TEXT NOT NULL UNIQUE,
  size INTEGER CHECK (size IS NULL OR size >= 0),
  sha256 TEXT,
  client_version TEXT NOT NULL,
  launcher_version TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('created', 'uploading', 'complete', 'failed', 'deleted')),
  submitted_at TEXT,
  expires_at TEXT NOT NULL,
  downloaded_at TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_diagnostics_expiry ON diagnostic_submissions(expires_at);
