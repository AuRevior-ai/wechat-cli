export interface WorkerVariables {
  requestId: string;
}

export interface Env {
  DB: D1Database;
  DIAGNOSTICS: R2Bucket;

  ENVIRONMENT: string;
  LEASE_SIGNING_KEY_ID: string;
  CONTACT_ENCRYPTION_KEY_VERSION: string;
  MAX_DIAGNOSTIC_BYTES: string;

  LICENSE_KEY_PEPPER: string;
  DEVICE_TOKEN_PEPPER: string;
  ADMIN_TOKEN_PEPPER: string;
  CONTACT_LOOKUP_PEPPER: string;
  CONTACT_ENCRYPTION_KEY_V1: string;
  LEASE_SIGNING_PRIVATE_KEY: string;
  DOWNLOAD_TICKET_SECRET: string;
  GITHUB_RELEASE_READ_TOKEN: string;
}

export type LicenseStatus = "active" | "suspended" | "revoked";
export type DeviceStatus = "active" | "disabled" | "unbound";
export type ReleaseChannel = "stable" | "beta";

export interface LicenseRow {
  id: string;
  key_digest: string;
  key_hint: string;
  status: LicenseStatus;
  max_devices: number;
  release_channel: ReleaseChannel;
  revision: number;
  created_at: string;
  updated_at: string;
  suspended_at: string | null;
  revoked_at: string | null;
  created_by_admin_id: string | null;
}

export interface DeviceRow {
  id: string;
  license_id: string;
  client_install_id_digest: string;
  fingerprint_digest: string | null;
  display_name: string;
  status: DeviceStatus;
  token_id: string;
  token_secret_digest: string;
  token_version: number;
  device_revision: number;
  first_activated_at: string;
  last_validated_at: string | null;
  last_app_version: string | null;
  last_launcher_version: string | null;
  disabled_at: string | null;
  unbound_at: string | null;
}

export interface ReleaseRow {
  id: string;
  version: string;
  channel: ReleaseChannel;
  manifest_content: ArrayBuffer;
  manifest_signature: ArrayBuffer;
  manifest_sha256: string;
  package_sha256: string;
  package_size: number;
  github_repository: string;
  github_release_id: string;
  github_asset_id: string;
  github_asset_name: string;
  rollout_percentage: number;
  rollout_seed: string;
  paused: number;
  enabled: number;
  published_at: string;
  created_at: string;
}

export interface AuthenticatedDevice {
  license: LicenseRow;
  device: DeviceRow;
}

export interface AuthenticatedAdmin {
  id: string;
  scopes: Set<string>;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    retryable: boolean;
    request_id: string;
    details?: Record<string, unknown>;
  };
}
