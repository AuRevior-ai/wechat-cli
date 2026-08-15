import type { Hono } from "hono";

import {
  AccessJwtVerifier,
  fetchAccessJwks,
  type VerifiedAccessIdentity,
} from "./access_identity";
export { AccessJwtVerifier, fetchAccessJwks } from "./access_identity";

import {
  bytesToBase64Url,
  constantTimeEqual,
  randomId,
  randomToken,
  sha256Hex,
} from "./crypto";
import { ApiError, readJsonObject, requiredString } from "./http";
import { enforceAdminLoginRateLimit } from "./security_policy";
import { versionedHmacDigest } from "./secret_versions";
import { writeAudit } from "./service";
import type { Env, WorkerVariables } from "./types";

export type VerifiedAdminIdentity = VerifiedAccessIdentity;

export interface AdminIdentityVerifier {
  verify(assertion: string): Promise<VerifiedAdminIdentity>;
}

export interface AdminLoginRouteOptions {
  adminIdentityVerifier?: AdminIdentityVerifier;
}

type WorkerApp = Hono<{ Bindings: Env; Variables: WorkerVariables }>;

function adminLoginError(code: string, message: string): ApiError {
  return new ApiError(code, message, { status: 401, retryable: false });
}

function invalidAdminIdentity(): ApiError {
  return adminLoginError("ADMIN_IDENTITY_INVALID", "管理员身份断言无效。");
}

function parseScopes(value: unknown): string[] {
  let parsed = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      parsed = [];
    }
  }
  if (
    !Array.isArray(parsed) ||
    parsed.length === 0 ||
    parsed.length > 64 ||
    !parsed.every(
      (scope) => typeof scope === "string" && /^[A-Za-z0-9:*._-]{1,128}$/u.test(scope),
    )
  ) {
    throw adminLoginError("ADMIN_PRINCIPAL_INVALID", "管理员权限数据无效。");
  }
  return parsed as string[];
}

export async function adminLoginChallenge(verifier: string): Promise<string> {
  if (
    typeof verifier !== "string" ||
    verifier.length < 43 ||
    verifier.length > 128 ||
    !/^[A-Za-z0-9_-]+$/u.test(verifier)
  ) {
    throw adminLoginError("ADMIN_LOGIN_CODE_INVALID", "管理员登录校验值无效。");
  }
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return bytesToBase64Url(new Uint8Array(digest));
}

export async function createAdminLoginCode(
  env: Env,
  options: {
    identity: string;
    subject: string;
    challenge: string;
    now?: Date;
  },
): Promise<{ code: string; expires_at: string; principal_id: string }> {
  const identity = options.identity.trim().toLowerCase();
  if (
    !identity ||
    identity.length > 512 ||
    typeof options.subject !== "string" ||
    !options.subject ||
    options.subject.length > 512 ||
    !/^[A-Za-z0-9_-]{43}$/u.test(options.challenge)
  ) {
    throw adminLoginError("ADMIN_IDENTITY_INVALID", "管理员身份断言无效。");
  }
  const principal = await env.DB.prepare(
    `SELECT id, identity, scopes_json, status
       FROM admin_principals
      WHERE identity = ?
      LIMIT 1`,
  )
    .bind(identity)
    .first<Record<string, unknown>>();
  if (principal === null || principal.status !== "active") {
    throw adminLoginError("ADMIN_PRINCIPAL_DENIED", "管理员身份未获授权。");
  }
  parseScopes(principal.scopes_json);
  const now = options.now ?? new Date();
  const createdAt = now.toISOString();
  const expiresAt = new Date(now.getTime() + 2 * 60 * 1000).toISOString();
  const code = randomId("wcal_", 24);
  const challengeDigest = await sha256Hex(`admin-login\u0000${options.challenge}`);
  await env.DB.prepare(
    `INSERT INTO admin_login_codes (
       id, principal_id, challenge_digest, expires_at, used_at, created_at
     ) VALUES (?, ?, ?, ?, NULL, ?)`,
  )
    .bind(code, String(principal.id), challengeDigest, expiresAt, createdAt)
    .run();
  return { code, expires_at: expiresAt, principal_id: String(principal.id) };
}

export async function exchangeAdminLoginCode(
  env: Env,
  options: { code: string; verifier: string; now?: Date },
): Promise<{
  session_token: string;
  authenticated_at: string;
  expires_at: string;
  principal_id: string;
}> {
  if (!/^wcal_[A-Za-z0-9_-]{20,128}$/u.test(options.code)) {
    throw adminLoginError("ADMIN_LOGIN_CODE_INVALID", "管理员登录代码无效。");
  }
  const row = await env.DB.prepare(
    `SELECT c.id, c.principal_id, c.challenge_digest, c.expires_at, c.used_at,
            p.scopes_json, p.status AS principal_status
       FROM admin_login_codes c
       JOIN admin_principals p ON p.id = c.principal_id
      WHERE c.id = ?
      LIMIT 1`,
  )
    .bind(options.code)
    .first<Record<string, unknown>>();
  const now = options.now ?? new Date();
  const authenticatedAt = now.toISOString();
  if (
    row === null ||
    row.used_at !== null ||
    row.principal_status !== "active" ||
    typeof row.expires_at !== "string" ||
    row.expires_at <= authenticatedAt
  ) {
    throw adminLoginError("ADMIN_LOGIN_CODE_INVALID", "管理员登录代码无效或已过期。");
  }
  const challenge = await adminLoginChallenge(options.verifier);
  const challengeDigest = await sha256Hex(`admin-login\u0000${challenge}`);
  if (!constantTimeEqual(challengeDigest, String(row.challenge_digest ?? ""))) {
    throw adminLoginError("ADMIN_LOGIN_CODE_INVALID", "管理员登录校验失败。");
  }
  const consumed = await env.DB.prepare(
    `UPDATE admin_login_codes
        SET used_at = ?
      WHERE id = ? AND used_at IS NULL`,
  )
    .bind(authenticatedAt, options.code)
    .run();
  if (Number(consumed.meta.changes ?? 0) !== 1) {
    throw adminLoginError("ADMIN_LOGIN_CODE_INVALID", "管理员登录代码已使用。");
  }
  const scopes = parseScopes(row.scopes_json);
  const tokenId = randomId("adms_", 16);
  const tokenSecret = randomToken(32);
  const sessionToken = `wcas_${tokenId}.${tokenSecret}`;
  const tokenDigest = await versionedHmacDigest(
    env,
    "admin-session-pepper",
    tokenSecret,
  );
  const sessionId = randomId("ases_", 16);
  const expiresAt = new Date(now.getTime() + 30 * 60 * 1000).toISOString();
  await env.DB.prepare(
    `INSERT INTO admin_sessions (
       id, token_id, token_digest, token_secret_version, principal_id, scopes_json,
       authenticated_at, expires_at, status, created_at, last_used_at, revoked_at
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, NULL, NULL)`,
  )
    .bind(
      sessionId,
      tokenId,
      tokenDigest.digest,
      tokenDigest.version,
      String(row.principal_id),
      JSON.stringify(scopes),
      authenticatedAt,
      expiresAt,
      authenticatedAt,
    )
    .run();
  return {
    session_token: sessionToken,
    authenticated_at: authenticatedAt,
    expires_at: expiresAt,
    principal_id: String(row.principal_id),
  };
}

const accessVerifierCache = new Map<string, AccessJwtVerifier>();

export function adminIdentityVerifierFromEnv(env: Env): AccessJwtVerifier {
  const issuer = env.ACCESS_JWT_ISSUER;
  const jwksUrl = env.ACCESS_JWKS_URL;
  const audiencesRaw =
    env.ENVIRONMENT === "production"
      ? env.ACCESS_HUMAN_AUDIENCES
      : (env.ACCESS_HUMAN_AUDIENCES ?? env.ACCESS_AUDIENCES);
  const identityClaim =
    env.ENVIRONMENT === "production"
      ? env.ACCESS_HUMAN_IDENTITY_CLAIM
      : (env.ACCESS_HUMAN_IDENTITY_CLAIM ?? env.ACCESS_IDENTITY_CLAIM);
  if (
    typeof issuer !== "string" ||
    typeof jwksUrl !== "string" ||
    typeof audiencesRaw !== "string" ||
    typeof identityClaim !== "string"
  ) {
    throw new ApiError("ADMIN_LOGIN_CONFIG_INVALID", "管理员登录身份配置未完成。", {
      status: 503,
      retryable: false,
    });
  }
  const audiences = audiencesRaw
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  const cacheKey = JSON.stringify([issuer, jwksUrl, audiences, identityClaim]);
  const existing = accessVerifierCache.get(cacheKey);
  if (existing !== undefined) return existing;
  const verifier = new AccessJwtVerifier({
    issuer,
    jwksUrl,
    audiences,
    identityClaim,
    fetchJwks: fetchAccessJwks,
  });
  accessVerifierCache.set(cacheKey, verifier);
  return verifier;
}

function exactAdminLoginOrigin(env: Env, requestUrl: string): void {
  const allowed = env.ACCESS_ADMIN_ORIGIN;
  if (typeof allowed !== "string" || allowed.length === 0) {
    throw new ApiError("ADMIN_LOGIN_CONFIG_INVALID", "管理员登录入口未配置。", {
      status: 503,
      retryable: false,
    });
  }
  let requestOrigin: string;
  let allowedOrigin: string;
  try {
    requestOrigin = new URL(requestUrl).origin;
    const parsedAllowed = new URL(allowed);
    if (
      parsedAllowed.protocol !== "https:" ||
      parsedAllowed.username ||
      parsedAllowed.password ||
      parsedAllowed.pathname !== "/" ||
      parsedAllowed.search ||
      parsedAllowed.hash
    ) {
      throw new TypeError("invalid Access admin origin");
    }
    allowedOrigin = parsedAllowed.origin;
  } catch (error) {
    throw new ApiError("ADMIN_LOGIN_CONFIG_INVALID", "管理员登录入口配置无效。", {
      status: 503,
      retryable: false,
      cause: error,
    });
  }
  if (requestOrigin !== allowedOrigin) {
    throw new ApiError("ADMIN_LOGIN_ORIGIN_INVALID", "管理员登录入口来源不受信任。", {
      status: 403,
      retryable: false,
    });
  }
}

function loopbackCallback(value: string): URL {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch (error) {
    throw new ApiError("ADMIN_LOGIN_CALLBACK_INVALID", "管理员登录回调地址无效。", {
      status: 400,
      cause: error,
    });
  }
  const port = Number(parsed.port);
  if (
    parsed.protocol !== "http:" ||
    parsed.hostname !== "127.0.0.1" ||
    !Number.isInteger(port) ||
    port < 1024 ||
    port > 65535 ||
    parsed.pathname !== "/callback" ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash
  ) {
    throw new ApiError("ADMIN_LOGIN_CALLBACK_INVALID", "管理员登录回调必须是 127.0.0.1 临时端口。", {
      status: 400,
      retryable: false,
    });
  }
  return parsed;
}

export function registerAdminLoginRoutes(
  app: WorkerApp,
  options: AdminLoginRouteOptions = {},
): void {
  app.get("/v1/admin/login/start", async (c) => {
    exactAdminLoginOrigin(c.env, c.req.url);
    await enforceAdminLoginRateLimit(c);
    const assertion = c.req.header("Cf-Access-Jwt-Assertion");
    if (typeof assertion !== "string" || assertion.length === 0) {
      throw invalidAdminIdentity();
    }
    const challenge = c.req.query("challenge");
    const redirectUri = c.req.query("redirect_uri");
    const state = c.req.query("state");
    if (
      typeof challenge !== "string" ||
      !/^[A-Za-z0-9_-]{43}$/u.test(challenge) ||
      typeof redirectUri !== "string" ||
      typeof state !== "string" ||
      !/^[A-Za-z0-9_-]{20,256}$/u.test(state)
    ) {
      throw new ApiError("INVALID_REQUEST", "管理员登录请求参数无效。", { status: 400 });
    }
    const callback = loopbackCallback(redirectUri);
    const verifier = options.adminIdentityVerifier ?? adminIdentityVerifierFromEnv(c.env);
    const verified = await verifier.verify(assertion);
    const issued = await createAdminLoginCode(c.env, {
      identity: verified.identity,
      subject: verified.subject,
      challenge,
    });
    await writeAudit(c.env, {
      actorType: "admin",
      actorId: issued.principal_id,
      action: "admin.login.code_issued",
      targetType: "admin_principal",
      targetId: issued.principal_id,
      result: "success",
      requestId: c.get("requestId"),
      metadata: { access_subject: verified.subject },
    });
    callback.searchParams.set("code", issued.code);
    callback.searchParams.set("state", state);
    return c.redirect(callback.toString(), 302);
  });

  app.post("/v1/admin/login/exchange", async (c) => {
    exactAdminLoginOrigin(c.env, c.req.url);
    await enforceAdminLoginRateLimit(c);
    const request = await readJsonObject(c.req.raw);
    const code = requiredString(request, "code", { minimum: 20, maximum: 160 });
    const verifier = requiredString(request, "verifier", { minimum: 43, maximum: 128 });
    const session = await exchangeAdminLoginCode(c.env, { code, verifier });
    await writeAudit(c.env, {
      actorType: "admin",
      actorId: session.principal_id,
      action: "admin.session.issued",
      targetType: "admin_principal",
      targetId: session.principal_id,
      result: "success",
      requestId: c.get("requestId"),
      metadata: { expires_at: session.expires_at },
    });
    return c.json(session);
  });
}
