import { constantTimeEqual, hmacSha256Hex } from "./crypto";
import { ApiError } from "./http";
import type { Env } from "./types";

export type SecretPurpose =
  | "license-key-pepper"
  | "device-token-pepper"
  | "admin-session-pepper"
  | "contact-lookup-pepper"
  | "download-ticket-secret"
  | "diagnostic-upload-secret"
  | "rate-limit-pepper";

const PURPOSE_PREFIX: Record<SecretPurpose, string> = {
  "license-key-pepper": "LICENSE_KEY_PEPPER",
  "device-token-pepper": "DEVICE_TOKEN_PEPPER",
  "admin-session-pepper": "ADMIN_SESSION_PEPPER",
  "contact-lookup-pepper": "CONTACT_LOOKUP_PEPPER",
  "download-ticket-secret": "DOWNLOAD_TICKET_SECRET",
  "diagnostic-upload-secret": "DIAGNOSTIC_UPLOAD_SECRET",
  "rate-limit-pepper": "RATE_LIMIT_PEPPER",
};

export interface VersionedSecretSet {
  currentVersion: number;
  readableVersions: number[];
  value(version: number): string;
  current(): { version: number; value: string };
}

function invalidSecretConfig(message: string): ApiError {
  return new ApiError("SECRET_VERSION_CONFIG_INVALID", message, {
    status: 500,
    retryable: false,
  });
}

function versionNumber(value: unknown, name: string): number {
  if (typeof value !== "string" || !/^\d{1,3}$/u.test(value)) {
    throw invalidSecretConfig(`${name} 配置无效。`);
  }
  const version = Number(value);
  if (!Number.isSafeInteger(version) || version < 1 || version > 999) {
    throw invalidSecretConfig(`${name} 配置无效。`);
  }
  return version;
}

function parseReadableVersions(value: unknown, name: string): number[] {
  if (typeof value !== "string" || value.length === 0 || value.length > 64) {
    throw invalidSecretConfig(`${name} 配置无效。`);
  }
  const raw = value.split(",").map((item) => item.trim());
  if (raw.length === 0 || raw.length > 8 || raw.some((item) => item.length === 0)) {
    throw invalidSecretConfig(`${name} 配置无效。`);
  }
  const versions = raw.map((item) => versionNumber(item, name));
  if (new Set(versions).size !== versions.length) {
    throw invalidSecretConfig(`${name} 包含重复版本。`);
  }
  return [...versions].sort((left, right) => left - right);
}

export function versionedSecretSet(
  env: Env,
  purpose: SecretPurpose,
): VersionedSecretSet {
  const prefix = PURPOSE_PREFIX[purpose];
  const values = env as unknown as Record<string, unknown>;
  const currentVersion = versionNumber(
    values[`${prefix}_CURRENT_VERSION`],
    `${prefix}_CURRENT_VERSION`,
  );
  const readableVersions = parseReadableVersions(
    values[`${prefix}_READABLE_VERSIONS`],
    `${prefix}_READABLE_VERSIONS`,
  );
  if (!readableVersions.includes(currentVersion)) {
    throw invalidSecretConfig(`${prefix} 当前版本必须包含在 readable versions 中。`);
  }
  const secrets = new Map<number, string>();
  for (const version of readableVersions) {
    const secret = values[`${prefix}_V${version}`];
    if (typeof secret !== "string" || secret.length < 16 || secret.length > 16_384) {
      throw invalidSecretConfig(`${prefix}_V${version} 缺失或长度无效。`);
    }
    secrets.set(version, secret);
  }
  return {
    currentVersion,
    readableVersions: [...readableVersions],
    value(version: number): string {
      if (!readableVersions.includes(version)) {
        throw new ApiError(
          "SECRET_VERSION_NOT_READABLE",
          `${purpose} 版本 ${version} 已不可读。`,
          { status: 401, retryable: false },
        );
      }
      const secret = secrets.get(version);
      if (secret === undefined) {
        throw invalidSecretConfig(`${prefix}_V${version} 缺失。`);
      }
      return secret;
    },
    current(): { version: number; value: string } {
      return { version: currentVersion, value: this.value(currentVersion) };
    },
  };
}

export async function versionedHmacDigest(
  env: Env,
  purpose: SecretPurpose,
  message: string,
): Promise<{ version: number; digest: string }> {
  const current = versionedSecretSet(env, purpose).current();
  return {
    version: current.version,
    digest: await hmacSha256Hex(current.value, message),
  };
}

export async function verifyVersionedHmacDigest(
  env: Env,
  purpose: SecretPurpose,
  version: number,
  message: string,
  expectedDigest: string,
): Promise<boolean> {
  const secret = versionedSecretSet(env, purpose).value(version);
  const actual = await hmacSha256Hex(secret, message);
  return constantTimeEqual(actual, expectedDigest);
}

export async function readableHmacDigests(
  env: Env,
  purpose: SecretPurpose,
  message: string,
): Promise<Array<{ version: number; digest: string }>> {
  const set = versionedSecretSet(env, purpose);
  return Promise.all(
    set.readableVersions.map(async (version) => ({
      version,
      digest: await hmacSha256Hex(set.value(version), message),
    })),
  );
}
