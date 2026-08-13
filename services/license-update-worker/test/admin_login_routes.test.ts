import { describe, expect, it, vi } from "vitest";

import { createApp } from "../src/index";
import { sha256Hex } from "../src/crypto";
import type { Env } from "../src/types";

type LoginCode = {
  id: string;
  principal_id: string;
  challenge_digest: string;
  expires_at: string;
  used_at: string | null;
  created_at: string;
};

function routeEnv() {
  const principal = {
    id: "prn_route_admin",
    identity: "admin@example.com",
    scopes_json: JSON.stringify(["licenses:read", "licenses:write"]),
    status: "active",
  };
  const codes = new Map<string, LoginCode>();
  const sessions: Record<string, unknown>[] = [];
  const db = {
    prepare(statement: string) {
      let bindings: unknown[] = [];
      return {
        bind(...values: unknown[]) {
          bindings = values;
          return this;
        },
        async first<T>() {
          if (statement.includes("INSERT INTO rate_limit_windows")) {
            return { count: 1 } as T;
          }
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
          throw new Error(`unexpected first query: ${statement}`);
        },
        async run() {
          if (statement.includes("INSERT INTO admin_login_codes")) {
            const [id, principalId, challengeDigest, expiresAt, createdAt] = bindings.map(String) as [
              string,
              string,
              string,
              string,
              string,
            ];
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
            sessions.push({ statement, bindings: [...bindings] });
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
  return {
    env: {
      DB: db,
      ENVIRONMENT: "local",
      ACCESS_ADMIN_ORIGIN: "https://admin.example.com",
      ADMIN_SESSION_PEPPER_CURRENT_VERSION: "1",
      ADMIN_SESSION_PEPPER_READABLE_VERSIONS: "1",
      ADMIN_SESSION_PEPPER_V1: "session-pepper-route-test",
      RATE_LIMIT_PEPPER_CURRENT_VERSION: "1",
      RATE_LIMIT_PEPPER_READABLE_VERSIONS: "1",
      RATE_LIMIT_PEPPER_V1: "rate-limit-pepper-login-route-tests",
    } as unknown as Env,
    codes,
    sessions,
  };
}

async function challenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  const bytes = new Uint8Array(digest);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/u, "");
}

describe("administrator browser login routes", () => {
  it("requires verified Access identity and redirects only to exact loopback callback", async () => {
    const { env, codes } = routeEnv();
    const verify = vi.fn(async (assertion: string) => {
      expect(assertion).toBe("signed-access-assertion");
      return { subject: "access-subject-1", identity: "admin@example.com" };
    });
    const app = (createApp as unknown as (options: unknown) => ReturnType<typeof createApp>)({
      adminIdentityVerifier: { verify },
    });
    const verifier = "a".repeat(64);
    const pkce = await challenge(verifier);
    const url = new URL("https://admin.example.com/v1/admin/login/start");
    url.searchParams.set("challenge", pkce);
    url.searchParams.set("redirect_uri", "http://127.0.0.1:54321/callback");
    url.searchParams.set("state", "state_abcdefghijklmnop123456");

    const response = await app.request(
      url.toString(),
      { headers: { "Cf-Access-Jwt-Assertion": "signed-access-assertion" } },
      env,
    );

    expect(response.status).toBe(302);
    expect(verify).toHaveBeenCalledTimes(1);
    const location = new URL(response.headers.get("Location")!);
    expect(location.origin).toBe("http://127.0.0.1:54321");
    expect(location.pathname).toBe("/callback");
    expect(location.searchParams.get("state")).toBe("state_abcdefghijklmnop123456");
    expect(location.searchParams.get("code")).toMatch(/^wcal_/u);
    expect(codes.size).toBe(1);
  });

  it("rejects workers.dev/alternate origin and missing Access assertion before DB issuance", async () => {
    const { env, codes } = routeEnv();
    const verify = vi.fn(async () => ({
      subject: "access-subject-1",
      identity: "admin@example.com",
    }));
    const app = (createApp as unknown as (options: unknown) => ReturnType<typeof createApp>)({
      adminIdentityVerifier: { verify },
    });
    const verifier = "b".repeat(64);
    const pkce = await challenge(verifier);
    const query = `challenge=${encodeURIComponent(pkce)}&redirect_uri=${encodeURIComponent(
      "http://127.0.0.1:54321/callback",
    )}&state=state_abcdefghijklmnop123456`;

    const wrongOrigin = await app.request(
      `https://worker-name.workers.dev/v1/admin/login/start?${query}`,
      { headers: { "Cf-Access-Jwt-Assertion": "signed-access-assertion" } },
      env,
    );
    expect(wrongOrigin.status).toBe(403);
    await expect(wrongOrigin.json()).resolves.toMatchObject({
      error: { code: "ADMIN_LOGIN_ORIGIN_INVALID" },
    });

    const missingAssertion = await app.request(
      `https://admin.example.com/v1/admin/login/start?${query}`,
      {},
      env,
    );
    expect(missingAssertion.status).toBe(401);
    expect(verify).not.toHaveBeenCalled();
    expect(codes.size).toBe(0);
  });

  it("exchanges a one-time code and verifier without requiring an Access assertion", async () => {
    const { env, sessions } = routeEnv();
    const verify = vi.fn(async () => ({
      subject: "access-subject-1",
      identity: "admin@example.com",
    }));
    const app = (createApp as unknown as (options: unknown) => ReturnType<typeof createApp>)({
      adminIdentityVerifier: { verify },
    });
    const verifier = "c".repeat(64);
    const pkce = await challenge(verifier);
    const startUrl = new URL("https://admin.example.com/v1/admin/login/start");
    startUrl.searchParams.set("challenge", pkce);
    startUrl.searchParams.set("redirect_uri", "http://127.0.0.1:54321/callback");
    startUrl.searchParams.set("state", "state_abcdefghijklmnop123456");
    const start = await app.request(
      startUrl.toString(),
      { headers: { "Cf-Access-Jwt-Assertion": "signed-access-assertion" } },
      env,
    );
    expect(start.status).toBe(302);
    const code = new URL(start.headers.get("Location")!).searchParams.get("code")!;

    const exchange = await app.request(
      "https://admin.example.com/v1/admin/login/exchange",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, verifier }),
      },
      env,
    );

    expect(exchange.status).toBe(200);
    const payload = await exchange.json<Record<string, unknown>>();
    expect(payload.session_token).toMatch(/^wcas_/u);
    expect(payload.principal_id).toBe("prn_route_admin");
    expect(String(payload.expires_at)).not.toBe("");
    expect(sessions).toHaveLength(1);
    expect(JSON.stringify(payload)).not.toContain(await sha256Hex("signed-access-assertion"));
  });
});
