CREATE TABLE automation_principals (
  id TEXT PRIMARY KEY,
  identity TEXT NOT NULL UNIQUE,
  display_name TEXT,
  scopes_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
  created_at TEXT NOT NULL,
  revoked_at TEXT
);

ALTER TABLE audit_events RENAME TO audit_events_legacy;

CREATE TABLE audit_events (
  id TEXT PRIMARY KEY,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('admin', 'automation', 'license', 'device', 'system')),
  actor_id TEXT,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  result TEXT NOT NULL,
  request_id TEXT NOT NULL,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

INSERT INTO audit_events (
  id, actor_type, actor_id, action, target_type, target_id,
  result, request_id, metadata_json, created_at
)
SELECT
  id, actor_type, actor_id, action, target_type, target_id,
  result, request_id, metadata_json, created_at
FROM audit_events_legacy;

DROP TABLE audit_events_legacy;

CREATE INDEX idx_audit_events_created ON audit_events(created_at DESC);
CREATE INDEX idx_audit_events_target ON audit_events(target_type, target_id, created_at DESC);
