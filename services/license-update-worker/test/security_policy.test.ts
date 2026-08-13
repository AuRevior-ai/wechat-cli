import { describe, expect, it } from "vitest";

import { createApp } from "../src/index";
import { hmacSha256Hex } from "../src/crypto";
import { enforceRateLimit } from "../src/service";
import type { AuthenticatedAdmin, Env } from "../src/types";

type SecurityPolicyModule = {
  assertWorkerOriginAllowed?: (request: Request, env: Env) => void;
  enforceAdminRateLimit?: (
    context: unknown,
    admin: AuthenticatedAdmin,
    rateClass: "read" | "write" | "high-risk",
  ) => Promise<void>;
  enforceAdminLoginRateLimit?: (context: unknown) => Promise<void>;
};

async function policyModule(): Promise<Required<SecurityPolicyModule>> {
  const path = "../src/security_policy";
  let module: SecurityPolicyModule = {};
  try {
    module = (await import(path)) as SecurityPolicyModule;
  } catch {
    module = {};
  }
  expect(module.assertWorkerOriginAllowed).toBeTypeOf("function");
  expect(module.enforceAdminRateLimit).toBeTypeOf("function");
  expect(module.enforceAdminLoginRateLimit).toBeTypeOf("function");
  return module as Required<SecurityPolicyModule>;
}

function rateDb() {
  const counts = new Map<string, { window: string; count: number }>();
  const keys: string[] = [];
  const db = {
    prepare(statement: string) {
      let bindings: unknown[] = [];
      return {
        bind(...values: unknown[]) {
          bindings = values;
          return this;
        },
        async first<T>() {
          if (!statement.includes("INSERT INTO rate_limit_windows")) {
            throw new Error(`unexpected first query: ${statement}`);
          }
          const [key, windowStart] = bindings.map(String) as [string, string, string];
          keys.push(key);
          const existing = counts.get(key);
          const count = existing?.window === windowStart ? existing.count + 1 : 1;
          counts.set(key, { window: windowStart, count });
          return { count } as T;
        },
      };
    },
  } as unknown as D1Database;
  return { db, counts, keys };
}

function context(env: Env, options?: { ip?: string; path?: string }) {
  const ip = options?.ip ?? "203.0.113.10";
  const path = options?.path ?? "/v1/admin/releases";
  return {
    env,
    req: {
      raw: new Request(`https://api.example.test${path}`, {
        headers: { "CF-Connecting-IP": ip },
      }),
      header(name: string) {
        if (name.toLowerCase() === "cf-connecting-ip") return ip;
        return undefined;
      },
    },
  } as never;
}

describe("explicit Worker Origin contract", () => {
  it("rejects unexpected Origin on sensitive native routes before route authentication", async () => {
    const env = { ENVIRONMENT: "local" } as Env;
    for (const path of [
      "/v1/admin/releases",
      "/v1/updates/check",
      "/v1/licenses/activate",
      "/v1/diagnostics/session",
    ]) {
      const response = await createApp().request(
        `https://api.example.test${path}`,
        {
          method: path.endsWith("releases") ? "GET" : "POST",
          headers: { Origin: "https://evil.example" },
        },
        env,
      );
      expect(response.status, path).toBe(403);
      await expect(response.json()).resolves.toMatchObject({
        error: { code: "ORIGIN_NOT_ALLOWED" },
      });
      expect(response.headers.get("Access-Control-Allow-Origin")).not.toBe("*");
    }
  });

  it("does not add wildcard CORS and rejects native OPTIONS preflight", async () => {
    const response = await createApp().request(
      "https://api.example.test/v1/admin/releases",
      {
        method: "OPTIONS",
        headers: {
          Origin: "https://evil.example",
          "Access-Control-Request-Method": "GET",
        },
      },
      { ENVIRONMENT: "local" } as Env,
    );
    expect(response.status).toBe(403);
    expect(response.headers.get("Access-Control-Allow-Origin")).not.toBe("*");
  });

  it("allows no-Origin native requests to preserve the normal authentication boundary", async () => {
    const response = await createApp().request(
      "https://api.example.test/v1/admin/releases",
      {},
      { ENVIRONMENT: "local" } as Env,
    );
    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toMatchObject({
      error: { code: "ADMIN_TOKEN_INVALID" },
    });
  });
});

describe("purpose-separated rate limiting", () => {
  it("derives rate-limit identity only from RATE_LIMIT_PEPPER", async () => {
    const { db, keys } = rateDb();
    const env = {
      DB: db,
      RATE_LIMIT_PEPPER: "rate-limit-pepper-test-value",
      DEVICE_TOKEN_PEPPER: "different-device-token-pepper",
    } as Env;
    await enforceRateLimit(context(env), {
      name: "purpose-test",
      maximum: 5,
      windowSeconds: 60,
      identity: "principal-1",
    });

    const expectedDigest = await hmacSha256Hex(
      "rate-limit-pepper-test-value",
      "rate-limit\u0000principal-1",
    );
    const wrongDigest = await hmacSha256Hex(
      "different-device-token-pepper",
      "rate-limit\u0000principal-1",
    );
    expect(keys[0]).toBe(`purpose-test:${expectedDigest}`);
    expect(keys[0]).not.toContain(wrongDigest);
  });

  it("aggregates login attempts across start and exchange paths at 5 per 300 seconds per IP", async () => {
    const module = await policyModule();
    const { db } = rateDb();
    const env = {
      DB: db,
      RATE_LIMIT_PEPPER: "rate-limit-pepper-login-value",
    } as Env;
    for (const path of [
      "/v1/admin/login/start",
      "/v1/admin/login/exchange",
      "/v1/admin/login/start",
      "/v1/admin/login/exchange",
      "/v1/admin/login/start",
    ]) {
      await expect(module.enforceAdminLoginRateLimit(context(env, { path }))).resolves.toBeUndefined();
    }
    await expect(
      module.enforceAdminLoginRateLimit(
        context(env, { path: "/v1/admin/login/exchange" }),
      ),
    ).rejects.toMatchObject({ code: "RATE_LIMITED", status: 429 });
  });

  it("aggregates admin read class across endpoints by principal", async () => {
    const module = await policyModule();
    const { db, keys } = rateDb();
    const env = {
      DB: db,
      RATE_LIMIT_PEPPER: "rate-limit-pepper-admin-value",
    } as Env;
    const admin: AuthenticatedAdmin = {
      id: "prn_admin_1",
      scopes: new Set(["*"]),
      authMode: "session",
      authenticatedAt: new Date().toISOString(),
    };

    await module.enforceAdminRateLimit(
      context(env, { path: "/v1/admin/licenses" }),
      admin,
      "read",
    );
    await module.enforceAdminRateLimit(
      context(env, { path: "/v1/admin/releases" }),
      admin,
      "read",
    );

    const principalKeys = keys.filter((key) => key.startsWith("admin-read-principal:"));
    expect(principalKeys).toHaveLength(2);
    expect(new Set(principalKeys).size).toBe(1);
  });
});
