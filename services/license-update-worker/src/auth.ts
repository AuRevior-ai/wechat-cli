import type { Context } from "hono";

import {
  constantTimeEqual,
  hmacSha256Hex,
  parseAdminToken,
  parseDeviceToken,
} from "./crypto";
import { ApiError } from "./http";
import type {
  AuthenticatedAdmin,
  AuthenticatedDevice,
  DeviceRow,
  Env,
  LicenseRow,
  WorkerVariables,
} from "./types";

function bearerValue(header: string | undefined): string {
  if (header === undefined) {
    throw new ApiError("INVALID_DEVICE_TOKEN", "缺少设备令牌。", { status: 401 });
  }
  const match = /^Bearer\s+(.+)$/iu.exec(header.trim());
  if (match === null || match[1] === undefined) {
    throw new ApiError("INVALID_DEVICE_TOKEN", "设备令牌格式无效。", { status: 401 });
  }
  return match[1];
}

export async function authenticateDevice(
  c: Context<{ Bindings: Env; Variables: WorkerVariables }, any, any>,
): Promise<AuthenticatedDevice> {
  const raw = bearerValue(c.req.header("Authorization"));
  let token: ReturnType<typeof parseDeviceToken>;
  try {
    token = parseDeviceToken(raw);
  } catch (error) {
    throw new ApiError("INVALID_DEVICE_TOKEN", "设备令牌格式无效。", {
      status: 401,
      cause: error,
    });
  }
  const row = await c.env.DB.prepare(
    `SELECT
       d.id, d.license_id, d.client_install_id_digest, d.fingerprint_digest,
       d.display_name, d.status, d.token_id, d.token_secret_digest,
       d.token_version, d.device_revision, d.first_activated_at,
       d.last_validated_at, d.last_app_version, d.last_launcher_version,
       d.disabled_at, d.unbound_at,
       l.id AS license_row_id, l.key_digest, l.key_hint,
       l.status AS license_status, l.max_devices, l.release_channel,
       l.revision, l.created_at AS license_created_at,
       l.updated_at AS license_updated_at, l.suspended_at, l.revoked_at,
       l.created_by_admin_id
     FROM devices d
     JOIN licenses l ON l.id = d.license_id
     WHERE d.token_id = ?
     LIMIT 1`,
  )
    .bind(token.tokenId)
    .first<Record<string, unknown>>();
  if (row === null) {
    throw new ApiError("INVALID_DEVICE_TOKEN", "设备令牌无效。", { status: 401 });
  }
  const expected = await hmacSha256Hex(
    c.env.DEVICE_TOKEN_PEPPER,
    token.tokenSecret,
  );
  const stored = String(row.token_secret_digest ?? "");
  if (!constantTimeEqual(expected, stored)) {
    throw new ApiError("INVALID_DEVICE_TOKEN", "设备令牌无效。", { status: 401 });
  }

  const device: DeviceRow = {
    id: String(row.id),
    license_id: String(row.license_id),
    client_install_id_digest: String(row.client_install_id_digest),
    fingerprint_digest:
      row.fingerprint_digest === null ? null : String(row.fingerprint_digest),
    display_name: String(row.display_name),
    status: row.status as DeviceRow["status"],
    token_id: String(row.token_id),
    token_secret_digest: stored,
    token_version: Number(row.token_version),
    device_revision: Number(row.device_revision),
    first_activated_at: String(row.first_activated_at),
    last_validated_at:
      row.last_validated_at === null ? null : String(row.last_validated_at),
    last_app_version:
      row.last_app_version === null ? null : String(row.last_app_version),
    last_launcher_version:
      row.last_launcher_version === null
        ? null
        : String(row.last_launcher_version),
    disabled_at: row.disabled_at === null ? null : String(row.disabled_at),
    unbound_at: row.unbound_at === null ? null : String(row.unbound_at),
  };
  const license: LicenseRow = {
    id: String(row.license_row_id),
    key_digest: String(row.key_digest),
    key_hint: String(row.key_hint),
    status: row.license_status as LicenseRow["status"],
    max_devices: Number(row.max_devices),
    release_channel: row.release_channel as LicenseRow["release_channel"],
    revision: Number(row.revision),
    created_at: String(row.license_created_at),
    updated_at: String(row.license_updated_at),
    suspended_at: row.suspended_at === null ? null : String(row.suspended_at),
    revoked_at: row.revoked_at === null ? null : String(row.revoked_at),
    created_by_admin_id:
      row.created_by_admin_id === null ? null : String(row.created_by_admin_id),
  };

  if (license.status === "suspended") {
    throw new ApiError("LICENSE_SUSPENDED", "许可证已暂停。", { status: 403 });
  }
  if (license.status === "revoked") {
    throw new ApiError("LICENSE_REVOKED", "许可证已吊销。", { status: 403 });
  }
  if (device.status === "unbound") {
    throw new ApiError("DEVICE_UNBOUND", "当前设备已解绑。", { status: 403 });
  }
  if (device.status === "disabled") {
    throw new ApiError("DEVICE_DISABLED", "当前设备已停用。", { status: 403 });
  }
  return { license, device };
}

export async function authenticateAdmin(
  c: Context<{ Bindings: Env; Variables: WorkerVariables }, any, any>,
  requiredScope: string,
): Promise<AuthenticatedAdmin> {
  const header = c.req.header("Authorization");
  const match = header === undefined ? null : /^Admin\s+(.+)$/iu.exec(header.trim());
  if (match === null || match[1] === undefined) {
    throw new ApiError("ADMIN_TOKEN_INVALID", "管理员令牌无效。", { status: 401 });
  }
  let token: ReturnType<typeof parseAdminToken>;
  try {
    token = parseAdminToken(match[1]);
  } catch (error) {
    throw new ApiError("ADMIN_TOKEN_INVALID", "管理员令牌无效。", {
      status: 401,
      cause: error,
    });
  }
  const row = await c.env.DB.prepare(
    `SELECT id, token_digest, scopes_json, status
       FROM admin_tokens
      WHERE token_id = ?
      LIMIT 1`,
  )
    .bind(token.tokenId)
    .first<Record<string, unknown>>();
  if (row === null || row.status !== "active") {
    throw new ApiError("ADMIN_TOKEN_INVALID", "管理员令牌无效。", { status: 401 });
  }
  const digest = await hmacSha256Hex(c.env.ADMIN_TOKEN_PEPPER, token.tokenSecret);
  if (!constantTimeEqual(digest, String(row.token_digest ?? ""))) {
    throw new ApiError("ADMIN_TOKEN_INVALID", "管理员令牌无效。", { status: 401 });
  }
  let scopes: unknown;
  try {
    scopes = JSON.parse(String(row.scopes_json));
  } catch {
    scopes = [];
  }
  if (!Array.isArray(scopes) || !scopes.every((scope) => typeof scope === "string")) {
    throw new ApiError("ADMIN_TOKEN_INVALID", "管理员权限数据无效。", { status: 401 });
  }
  const allowed = new Set(scopes as string[]);
  if (!allowed.has(requiredScope) && !allowed.has("*")) {
    throw new ApiError("ADMIN_SCOPE_DENIED", "管理员令牌权限不足。", { status: 403 });
  }
  await c.env.DB.prepare(
    "UPDATE admin_tokens SET last_used_at = ? WHERE id = ?",
  )
    .bind(new Date().toISOString(), String(row.id))
    .run();
  return { id: String(row.id), scopes: allowed };
}
