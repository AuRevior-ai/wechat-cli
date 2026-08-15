ALTER TABLE licenses ADD COLUMN key_secret_version INTEGER NOT NULL DEFAULT 1 CHECK (key_secret_version >= 1);
ALTER TABLE devices ADD COLUMN token_secret_version INTEGER NOT NULL DEFAULT 1 CHECK (token_secret_version >= 1);
ALTER TABLE admin_sessions ADD COLUMN token_secret_version INTEGER NOT NULL DEFAULT 1 CHECK (token_secret_version >= 1);
ALTER TABLE download_tickets ADD COLUMN secret_version INTEGER NOT NULL DEFAULT 1 CHECK (secret_version >= 1);
ALTER TABLE license_contacts ADD COLUMN lookup_secret_version INTEGER NOT NULL DEFAULT 1 CHECK (lookup_secret_version >= 1);
