ALTER TABLE diagnostic_submissions ADD COLUMN upload_expires_at TEXT;
ALTER TABLE diagnostic_submissions ADD COLUMN retention_expires_at TEXT;
ALTER TABLE diagnostic_submissions ADD COLUMN consent_version TEXT;

UPDATE diagnostic_submissions
   SET upload_expires_at = expires_at,
       retention_expires_at = expires_at,
       consent_version = 'legacy-v0'
 WHERE upload_expires_at IS NULL
    OR retention_expires_at IS NULL
    OR consent_version IS NULL;

CREATE INDEX idx_diagnostics_retention_expiry
  ON diagnostic_submissions(retention_expires_at);
