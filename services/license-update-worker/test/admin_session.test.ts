import { describe, expect, it } from "vitest";

import { authenticateAdmin } from "../src/auth";
import { hmacSha256Hex } from "../src/crypto";
import type { Env } from "../src/types";

type AdminSessionModule = {
  adminLoginChallenge?: (verifier: string) => Promise<string>;
  createAdminLoginCode?: (
    env: Env,
    options: {
      identity: string;
      subject: string;
      challenge: string;
      now?: Date;
    },
  ) => Promise<{ code: string; expires_at: string }>;
  exchangeAdminLoginCode?: (
    env: Env,
    options: { code: string; verifier: string; now?: Date },
  ) => Promise<{
    session_token: string;
    authenticated_at: string;
    expires_at: string;
    principal_id: string;
  }>;
};

async function adminSessionModule(): Promise<Required<AdminSessionModule>> {
  const path = "../src/admin_login";
  const module = (await import(path)) as AdminSessionModule;
  expect(module.adminLoginChallenge).toBeTypeOf("function");
  expect(module.createAdminLoginCode).toBeTypeOf("function");
  expect(module.exchangeAdminLoginCode).toBeTypeOf("function");
  return module as Required<AdminSessionModule>;
}

interface PrincipalState {
  id: string;
  identity: string;
  scopes_json: string;
  status: "active" | "revoked";
}

interface LoginCodeState {
  id: string;
  principal_id: string;
  challenge_digest: string;
  expires_at: string;
  used_at: string | null;
  created_at: string;
}

interface SessionState {
  id: string;
  token_id: string;
  token_digest: string;
  principal_id: string;
  scopes_json: string;
  authenticated_at: string;
  expires_at: string;
  status: "active" | "revoked";
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

function memoryEnv(options?: {
  environment?: string;
  principalStatus?: "active" | "revoked";
  allowLegacy?: string;
  breakGlass?: string;
}) {
  const principal: PrincipalState = {
    id: "prn_admin_1",
    identity: "admin@example.com",
    scopes_json: JSON.stringify(["licenses:read", "licenses:write", "releases:write"]),
    status: options?.principalStatus ?? "active",
  };
  const codes = new Map<string, LoginCodeState>();
  const sessions = new Map<string, SessionState>();
  const legacy = {
    id: "adm_legacy_1",
    token_id: "adm_abcdefghijkl",
    token_secret: "s".repeat(32),
    scopes_json: JSON.stringify(["licenses:read", "licenses:write"]),
    status: "active",
  };
  const adminTokenPepper = "legacy-admin-pepper";
  const adminSessionPepper = "session-pepper-v1";
  const legacyDigestPromise = hmacSha256Hex(adminTokenPepper, legacy.token_secret);
  const sql: string[] = [];
  const db = {
    prepare(statement: string) {
      sql.push(statement);
      let bindings: unknown[] = [];
      return {
        bind(...values: unknown[]) {
          bindings = values;
          return this;
        },
        async first<T>() {
          if (statement.includes("FROM admin_principals") && statement.includes("identity = ?")) {
            return (bindings[0] === principal.identity ? principal : null) as T;
          }
          if (statement.includes("FROM admin_login_codes")) {
            const code = codes.get(String(bindings[0]));
            if (code === undefined) return null as T;
            return {
              ...code,
              scopes_json: principal.scopes_json,
              principal_status: principal.status,
            } as T;
          }
          if (statement.includes("FROM admin_sessions") && statement.includes("token_id = ?")) {
            const session = [...sessions.values()].find((item) => item.token_id === bindings[0]);
            if (session === undefined) return null as T;
            return {
              ...session,
              principal_status: principal.status,
            } as T;
          }
          if (statement.includes("FROM admin_tokens")) {
            if (bindings[0] !== legacy.token_id) return null as T;
            return {
              id: legacy.id,
              token_digest: await legacyDigestPromise,
              scopes_json: legacy.scopes_json,
              status: legacy.status,
            } as T;
          }
          throw new Error(`unexpected first query: ${statement}`);
        },
        async run() {
          if (statement.includes("INSERT INTO admin_login_codes")) {
            const [id, principalId, challengeDigest, expiresAt, createdAt] = bindings.map(String) as [string, string, string, string, string];
            codes.set(id, {
              id,
              principal_id: principalId,
              challenge_digest: challengeDigest,
              expires_at: expiresAt,
              used_at: null,
              created_at: createdAt,
            });
            return { success: true, meta: { changes: 1 } };
          }
          if (statement.includes("UPDATE admin_login_codes") && statement.includes("used_at")) {
            const [usedAt, id] = bindings.map(String) as [string, string];
            const code = codes.get(id);
            if (code === undefined || code.used_at !== null) {
              return { success: true, meta: { changes: 0 } };
            }
            code.used_at = usedAt;
            return { success: true, meta: { changes: 1 } };
          }
          if (statement.includes("INSERT INTO admin_sessions")) {
            const [
              id,
              tokenId,
              tokenDigest,
              principalId,
              scopesJson,
              authenticatedAt,
              expiresAt,
              createdAt,
            ] = bindings.map(String) as [
              string,
              string,
              string,
              string,
              string,
              string,
              string,
              string,
            ];
            sessions.set(id, {
              id,
              token_id: tokenId,
              token_digest: tokenDigest,
              principal_id: principalId,
              scopes_json: scopesJson,
              authenticated_at: authenticatedAt,
              expires_at: expiresAt,
              status: "active",
              created_at: createdAt,
              last_used_at: null,
              revoked_at: null,
            });
            return { success: true, meta: { changes: 1 } };
          }
          if (statement.includes("UPDATE admin_sessions SET last_used_at")) {
            return { success: true, meta: { changes: 1 } };
          }
          if (statement.includes("UPDATE admin_tokens SET last_used_at")) {
            return { success: true, meta: { changes: 1 } };
          }
          if (statement.includes("INSERT INTO audit_events")) {
            return { success: true, meta: { changes: 1 } };
          }
          throw new Error(`unexpected run query: ${statement}`);
        },
      };
    },
  } as unknown as D1Database;

  const env = {
    DB: db,
    ENVIRONMENT: options?.environment ?? "local",
    ADMIN_TOKEN_PEPPER: adminTokenPepper,
    ADMIN_SESSION_PEPPER_V1: adminSessionPepper,
    ALLOW_LEGACY_ADMIN_AUTH: options?.allowLegacy,
    ADMIN_BREAK_GLASS_POLICY: options?.breakGlass,
  } as Env;
  return { env, principal, codes, sessions, legacy, sql };
}

function adminContext(env: Env, authorization: string) {
  return {
    env,
    req: {
      header(name: string) {
        return name.toLowerCase() === "authorization" ? authorization : undefined;
      },
    },
    get(name: string) {
      return name === "requestId" ? "req_admin_session_test" : undefined;
    },
  } as never;
}

describe("short-lived administrator sessions", () => {
  it("creates a short-lived challenge-bound one-time code for an active principal", async () => {
    const module = await adminSessionModule();
    const { env, codes } = memoryEnv();
    const verifier = "v".repeat(64);
    const challenge = await module.adminLoginChallenge!(verifier);

    const issued = await module.createAdminLoginCode!(env, {
      identity: "ADMIN@example.com",
      subject: "access-subject-1",
      challenge,
      now: new Date("2026-08-13T00:00:00Z"),
    });

    expect(issued.code).toMatch(/^wcal_[A-Za-z0-9_-]{20,}$/u);
    expect(issued.expires_at).toBe("2026-08-13T00:02:00.000Z");
    const stored = codes.get(issued.code)!;
    expect(stored.principal_id).toBe("prn_admin_1");
    expect(stored.challenge_digest).not.toContain(challenge);
    expect(stored.used_at).toBeNull();
  });

  it("exchanges the code once for a digest-only 30 minute session", async () => {
    const module = await adminSessionModule();
    const { env, codes, sessions } = memoryEnv();
    const verifier = "x".repeat(64);
    const challenge = await module.adminLoginChallenge!(verifier);
    const issued = await module.createAdminLoginCode!(env, {
      identity: "admin@example.com",
      subject: "access-subject-1",
      challenge,
      now: new Date("2026-08-13T00:00:00Z"),
    });

    const result = await module.exchangeAdminLoginCode!(env, {
      code: issued.code,
      verifier,
      now: new Date("2026-08-13T00:01:00Z"),
    });

    expect(result.session_token).toMatch(/^wcas_adms_[A-Za-z0-9_-]{12,64}\.[A-Za-z0-9_-]{32,}$/u);
    expect(result.authenticated_at).toBe("2026-08-13T00:01:00.000Z");
    expect(result.expires_at).toBe("2026-08-13T00:31:00.000Z");
    expect(codes.get(issued.code)?.used_at).toBe("2026-08-13T00:01:00.000Z");
    const stored = [...sessions.values()][0]!;
    expect(stored.token_digest).not.toContain(result.session_token);
    expect(stored.principal_id).toBe("prn_admin_1");

    await expect(
      module.exchangeAdminLoginCode!(env, {
        code: issued.code,
        verifier,
        now: new Date("2026-08-13T00:01:01Z"),
      }),
    ).rejects.toMatchObject({ code: "ADMIN_LOGIN_CODE_INVALID" });
  });

  it("rejects a verifier that does not match the stored challenge", async () => {
    const module = await adminSessionModule();
    const { env } = memoryEnv();
    const challenge = await module.adminLoginChallenge!("a".repeat(64));
    const issued = await module.createAdminLoginCode!(env, {
      identity: "admin@example.com",
      subject: "access-subject-1",
      challenge,
      now: new Date("2026-08-13T00:00:00Z"),
    });

    await expect(
      module.exchangeAdminLoginCode!(env, {
        code: issued.code,
        verifier: "b".repeat(64),
        now: new Date("2026-08-13T00:01:00Z"),
      }),
    ).rejects.toMatchObject({ code: "ADMIN_LOGIN_CODE_INVALID" });
  });

  it("authenticates wcas sessions and fails closed on revoke, expiry, scope, and stale recent-auth", async () => {
    const module = await adminSessionModule();
    const state = memoryEnv();
    const verifier = "c".repeat(64);
    const challenge = await module.adminLoginChallenge!(verifier);
    const issued = await module.createAdminLoginCode!(state.env, {
      identity: "admin@example.com",
      subject: "access-subject-1",
      challenge,
      now: new Date(),
    });
    const session = await module.exchangeAdminLoginCode!(state.env, {
      code: issued.code,
      verifier,
      now: new Date(),
    });

    await expect(
      authenticateAdmin(
        adminContext(state.env, `Admin ${session.session_token}`),
        "licenses:read",
      ),
    ).resolves.toMatchObject({ id: "prn_admin_1", authMode: "session" });

    await expect(
      authenticateAdmin(
        adminContext(state.env, `Admin ${session.session_token}`),
        "diagnostics:delete",
      ),
    ).rejects.toMatchObject({ code: "ADMIN_SCOPE_DENIED" });

    state.principal.status = "revoked";
    await expect(
      authenticateAdmin(
        adminContext(state.env, `Admin ${session.session_token}`),
        "licenses:read",
      ),
    ).rejects.toMatchObject({ code: "ADMIN_SESSION_INVALID" });
  });

  it("requires recent authentication for high-risk session use", async () => {
    const module = await adminSessionModule();
    const state = memoryEnv();
    const verifier = "d".repeat(64);
    const challenge = await module.adminLoginChallenge!(verifier);
    const issued = await module.createAdminLoginCode!(state.env, {
      identity: "admin@example.com",
      subject: "access-subject-1",
      challenge,
      now: new Date("2099-01-01T00:00:00Z"),
    });
    const session = await module.exchangeAdminLoginCode!(state.env, {
      code: issued.code,
      verifier,
      now: new Date("2099-01-01T00:00:00Z"),
    });
    const stored = [...state.sessions.values()][0]!;
    stored.authenticated_at = new Date(Date.now() - 11 * 60 * 1000).toISOString();
    stored.expires_at = new Date(Date.now() + 10 * 60 * 1000).toISOString();

    await expect(
      authenticateAdmin(
        adminContext(state.env, `Admin ${session.session_token}`),
        "licenses:write",
        { requireRecentAuthentication: true },
      ),
    ).rejects.toMatchObject({ code: "ADMIN_RECENT_AUTH_REQUIRED" });
  });

  it("denies legacy admin auth in production by default and only allows bounded break-glass policy", async () => {
    const denied = memoryEnv({ environment: "production" });
    const legacyToken = `wcadmin_${denied.legacy.token_id}.${denied.legacy.token_secret}`;
    await expect(
      authenticateAdmin(
        adminContext(denied.env, `Admin ${legacyToken}`),
        "licenses:read",
      ),
    ).rejects.toMatchObject({ code: "ADMIN_LEGACY_AUTH_DISABLED" });

    const now = new Date();
    const allowed = memoryEnv({
      environment: "production",
      breakGlass: JSON.stringify({
        reason: "incident-response-test",
        principal_id: "adm_legacy_1",
        scopes: ["licenses:read"],
        starts_at: new Date(now.getTime() - 60_000).toISOString(),
        expires_at: new Date(now.getTime() + 5 * 60_000).toISOString(),
      }),
    });
    const allowedToken = `wcadmin_${allowed.legacy.token_id}.${allowed.legacy.token_secret}`;
    await expect(
      authenticateAdmin(
        adminContext(allowed.env, `Admin ${allowedToken}`),
        "licenses:read",
      ),
    ).resolves.toMatchObject({ id: "adm_legacy_1", authMode: "legacy_break_glass" });
  });
});
