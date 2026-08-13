import type { Context } from "hono";

import {
  constantTimeEqual,
  hmacSha256Hex,
  parseAdminToken,
  parseDeviceToken,
} from "./crypto";
import { ApiError } from "./http";
import { verifyVersionedHmacDigest } from "./secret_versions";
import { writeAudit } from "./service";
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
       d.token_secret_version, d.token_version, d.device_revision, d.first_activated_at,
       d.last_validated_at, d.last_app_version, d.last_launcher_version,
       d.disabled_at, d.unbound_at,
       l.id AS license_row_id, l.key_digest, l.key_secret_version, l.key_hint,
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
  const stored = String(row.token_secret_digest ?? "");
  const tokenSecretVersion = Number(row.token_secret_version);
  if (
    !Number.isSafeInteger(tokenSecretVersion) ||
    tokenSecretVersion < 1 ||
    !(await verifyVersionedHmacDigest(
      c.env,
      "device-token-pepper",
      tokenSecretVersion,
      token.tokenSecret,
      stored,
    ))
  ) {
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
    token_secret_version: tokenSecretVersion,
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
    key_secret_version: Number(row.key_secret_version),
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

function parseScopeSet(value: unknown, invalidCode: string): Set<string> {
  let scopes: unknown;
  try {
    scopes = typeof value === "string" ? JSON.parse(value) : value;
  } catch {
    scopes = [];
  }
  if (
    !Array.isArray(scopes) ||
    scopes.length === 0 ||
    scopes.length > 64 ||
    !scopes.every((scope) => typeof scope === "string")
  ) {
    throw new ApiError(invalidCode, "管理员权限数据无效。", { status: 401 });
  }
  return new Set(scopes as string[]);
}

function parseAdminSessionToken(value: string): { tokenId: string; tokenSecret: string } {
  const match = /^wcas_(adms_[A-Za-z0-9_-]{12,64})\.([A-Za-z0-9_-]{32,256})$/u.exec(value);
  if (match === null || match[1] === undefined || match[2] === undefined) {
    throw new ApiError("ADMIN_SESSION_INVALID", "管理员会话无效。", { status: 401 });
  }
  return { tokenId: match[1], tokenSecret: match[2] };
}

interface BreakGlassPolicy {
  reason: string;
  principal_id: string;
  scopes: string[];
  starts_at: string;
  expires_at: string;
}

function productionBreakGlassPolicy(
  env: Env,
  requiredScope: string,
  now: Date,
): BreakGlassPolicy | null {
  const raw = env.ADMIN_BREAK_GLASS_POLICY;
  if (typeof raw !== "string" || raw.length === 0 || raw.length > 8192) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return null;
  const value = parsed as Record<string, unknown>;
  const reason = value.reason;
  const principalId = value.principal_id;
  const scopes = value.scopes;
  const startsAt = value.starts_at;
  const expiresAt = value.expires_at;
  if (
    typeof reason !== "string" ||
    reason.length < 8 ||
    reason.length > 512 ||
    typeof principalId !== "string" ||
    principalId.length === 0 ||
    !Array.isArray(scopes) ||
    !scopes.every((scope) => typeof scope === "string") ||
    typeof startsAt !== "string" ||
    typeof expiresAt !== "string"
  ) {
    return null;
  }
  const startMs = Date.parse(startsAt);
  const expiryMs = Date.parse(expiresAt);
  const nowMs = now.getTime();
  if (
    !Number.isFinite(startMs) ||
    !Number.isFinite(expiryMs) ||
    expiryMs <= startMs ||
    expiryMs - startMs > 4 * 60 * 60 * 1000 ||
    nowMs < startMs ||
    nowMs >= expiryMs ||
    (!scopes.includes(requiredScope) && !scopes.includes("*"))
  ) {
    return null;
  }
  return {
    reason,
    principal_id: principalId,
    scopes: scopes as string[],
    starts_at: startsAt,
    expires_at: expiresAt,
  };
}

async function authenticateAdminSession(
  c: Context<{ Bindings: Env; Variables: WorkerVariables }, any, any>,
  raw: string,
  requiredScope: string,
  options: { requireRecentAuthentication?: boolean },
): Promise<AuthenticatedAdmin> {
  const token = parseAdminSessionToken(raw);
  const row = await c.env.DB.prepare(
    `SELECT s.id, s.token_digest, s.token_secret_version, s.principal_id, s.scopes_json,
            s.authenticated_at, s.expires_at, s.status,
            p.status AS principal_status
       FROM admin_sessions s
       JOIN admin_principals p ON p.id = s.principal_id
      WHERE s.token_id = ?
      LIMIT 1`,
  )
    .bind(token.tokenId)
    .first<Record<string, unknown>>();
  const now = new Date();
  const nowIso = now.toISOString();
  if (
    row === null ||
    row.status !== "active" ||
    row.principal_status !== "active" ||
    typeof row.expires_at !== "string" ||
    row.expires_at <= nowIso
  ) {
    throw new ApiError("ADMIN_SESSION_INVALID", "管理员会话无效或已过期。", { status: 401 });
  }
  const tokenSecretVersion = Number(row.token_secret_version);
  if (
    !Number.isSafeInteger(tokenSecretVersion) ||
    tokenSecretVersion < 1 ||
    !(await verifyVersionedHmacDigest(
      c.env,
      "admin-session-pepper",
      tokenSecretVersion,
      token.tokenSecret,
      String(row.token_digest ?? ""),
    ))
  ) {
    throw new ApiError("ADMIN_SESSION_INVALID", "管理员会话无效。", { status: 401 });
  }
  const allowed = parseScopeSet(row.scopes_json, "ADMIN_SESSION_INVALID");
  if (!allowed.has(requiredScope) && !allowed.has("*")) {
    throw new ApiError("ADMIN_SCOPE_DENIED", "管理员会话权限不足。", { status: 403 });
  }
  const authenticatedAt = String(row.authenticated_at ?? "");
  const authenticatedMs = Date.parse(authenticatedAt);
  if (!Number.isFinite(authenticatedMs) || authenticatedMs > now.getTime() + 2 * 60 * 1000) {
    throw new ApiError("ADMIN_SESSION_INVALID", "管理员会话认证时间无效。", { status: 401 });
  }
  if (
    options.requireRecentAuthentication === true &&
    now.getTime() - authenticatedMs > 10 * 60 * 1000
  ) {
    throw new ApiError("ADMIN_RECENT_AUTH_REQUIRED", "该操作需要最近十分钟内重新认证。", {
      status: 401,
      retryable: false,
    });
  }
  await c.env.DB.prepare("UPDATE admin_sessions SET last_used_at = ? WHERE id = ?")
    .bind(nowIso, String(row.id))
    .run();
  return {
    id: String(row.principal_id),
    scopes: allowed,
    authMode: "session",
    authenticatedAt,
  };
}

async function authenticateLegacyAdmin(
  c: Context<{ Bindings: Env; Variables: WorkerVariables }, any, any>,
  raw: string,
  requiredScope: string,
): Promise<AuthenticatedAdmin> {
  const now = new Date();
  let mode: AuthenticatedAdmin["authMode"];
  let breakGlass: BreakGlassPolicy | null = null;
  if (c.env.ENVIRONMENT === "local") {
    mode = "legacy_local";
  } else if (c.env.ENVIRONMENT === "staging" && c.env.ALLOW_LEGACY_ADMIN_AUTH === "true") {
    mode = "legacy_staging";
  } else if (c.env.ENVIRONMENT === "production") {
    breakGlass = productionBreakGlassPolicy(c.env, requiredScope, now);
    if (breakGlass === null) {
      throw new ApiError("ADMIN_LEGACY_AUTH_DISABLED", "长期管理员令牌在当前环境已禁用。", {
        status: 401,
        retryable: false,
      });
    }
    mode = "legacy_break_glass";
  } else {
    throw new ApiError("ADMIN_LEGACY_AUTH_DISABLED", "长期管理员令牌在当前环境已禁用。", {
      status: 401,
      retryable: false,
    });
  }

  let token: ReturnType<typeof parseAdminToken>;
  try {
    token = parseAdminToken(raw);
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
  if (breakGlass !== null && breakGlass.principal_id !== String(row.id)) {
    throw new ApiError("ADMIN_LEGACY_AUTH_DISABLED", "临时 break-glass 授权与管理员不匹配。", {
      status: 401,
      retryable: false,
    });
  }
  const digest = await hmacSha256Hex(c.env.ADMIN_TOKEN_PEPPER, token.tokenSecret);
  if (!constantTimeEqual(digest, String(row.token_digest ?? ""))) {
    throw new ApiError("ADMIN_TOKEN_INVALID", "管理员令牌无效。", { status: 401 });
  }
  const allowed = parseScopeSet(row.scopes_json, "ADMIN_TOKEN_INVALID");
  if (!allowed.has(requiredScope) && !allowed.has("*")) {
    throw new ApiError("ADMIN_SCOPE_DENIED", "管理员令牌权限不足。", { status: 403 });
  }
  const nowIso = now.toISOString();
  await c.env.DB.prepare("UPDATE admin_tokens SET last_used_at = ? WHERE id = ?")
    .bind(nowIso, String(row.id))
    .run();
  if (mode === "legacy_break_glass" && breakGlass !== null) {
    await writeAudit(c.env, {
      actorType: "admin",
      actorId: String(row.id),
      action: "admin.break_glass.use",
      targetType: "admin_scope",
      targetId: requiredScope,
      result: "success",
      requestId: c.get("requestId"),
      metadata: {
        reason: breakGlass.reason,
        starts_at: breakGlass.starts_at,
        expires_at: breakGlass.expires_at,
        scope: requiredScope,
      },
    });
  }
  return {
    id: String(row.id),
    scopes: allowed,
    authMode: mode,
    authenticatedAt: nowIso,
  };
}

export async function authenticateAdmin(
  c: Context<{ Bindings: Env; Variables: WorkerVariables }, any, any>,
  requiredScope: string,
  options: { requireRecentAuthentication?: boolean } = {},
): Promise<AuthenticatedAdmin> {
  const header = c.req.header("Authorization");
  const match = header === undefined ? null : /^Admin\s+(.+)$/iu.exec(header.trim());
  if (match === null || match[1] === undefined) {
    throw new ApiError("ADMIN_TOKEN_INVALID", "管理员令牌无效。", { status: 401 });
  }
  const raw = match[1];
  if (raw.startsWith("wcas_")) {
    return authenticateAdminSession(c, raw, requiredScope, options);
  }
  return authenticateLegacyAdmin(c, raw, requiredScope);
}
