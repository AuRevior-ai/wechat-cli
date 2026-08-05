ALTER TABLE licenses ADD COLUMN generation_request_id TEXT;
ALTER TABLE licenses ADD COLUMN generation_index INTEGER;

CREATE UNIQUE INDEX idx_license_generation_request
  ON licenses(created_by_admin_id, generation_request_id, generation_index)
  WHERE generation_request_id IS NOT NULL;
