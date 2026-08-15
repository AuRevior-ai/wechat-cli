import { describe, expect, it, vi } from "vitest";

import { createApp } from "../src/index";
import { hmacSha256Hex, sha256Hex } from "../src/crypto";
import { assertHumanReleaseStateAuthority } from "../src/release_operations";
import type { AuthenticatedAutomation, Env } from "../src/types";

function automationIdentity(scopes = ["releases:upload", "releases:read", "releases:register"]): AuthenticatedAutomation {
  return {
    id: "automation_prod_1",
    identity: "release-automation-client",
    scopes: new Set(scopes),
    authMode: "access_service",
    authenticatedAt: "2026-08-15T08:00:00.000Z",
  };
}

function releaseDb() {
  const rows: Record<string, unknown>[] = [];
  const statements: string[] = [];
  const db = {
    prepare(statement: string) {
      statements.push(statement);
      let bindings: unknown[] = [];
      return {
        bind(...values: unknown[]) {
          bindings = values;
          return this;
        },
        async first<T>() {
          if (statement.includes("INSERT INTO idempotency_records")) {
            return null as T;
          }
          if (statement.includes("FROM releases") && statement.includes("channel = ?") && statement.includes("version = ?")) {
            return null as T;
          }
          throw new Error(`unexpected first query: ${statement} ${JSON.stringify(bindings)}`);
        },
        async all<T>() {
          if (statement.includes("FROM releases ORDER BY published_at")) {
            return { results: rows } as T;
          }
          throw new Error(`unexpected all query: ${statement}`);
        },
        async run() {
          if (statement.includes("INSERT OR IGNORE INTO idempotency_records")) {
            return { success: true, meta: { changes: 1 } };
          }
          if (statement.includes("INSERT INTO releases")) {
            rows.push({
              id: String(bindings[0]),
              version: String(bindings[1]),
              channel: String(bindings[2]),
              manifest_sha256: String(bindings[5]),
              package_sha256: String(bindings[6]),
              package_size: Number(bindings[7]),
              github_repository: String(bindings[8]),
              github_release_id: String(bindings[9]),
              github_asset_id: String(bindings[10]),
              github_asset_name: String(bindings[11]),
              distribution_backend: String(bindings[12]),
              distribution_object_key: bindings[13],
              rollout_percentage: Number(bindings[14]),
              paused: 1,
              enabled: 0,
              published_at: String(bindings[16]),
              created_at: String(bindings[17]),
            });
            return { success: true, meta: { changes: 1 } };
          }
          if (statement.includes("INSERT INTO audit_events") || statement.includes("UPDATE idempotency_records")) {
            return { success: true, meta: { changes: 1 } };
          }
          throw new Error(`unexpected run query: ${statement}`);
        },
      };
    },
  } as unknown as D1Database;
  return { db, rows, statements };
}

function env(): Env {
  const { db } = releaseDb();
  return {
    DB: db,
    ENVIRONMENT: "local",
    RATE_LIMIT_PEPPER_CURRENT_VERSION: "1",
    RATE_LIMIT_PEPPER_READABLE_VERSIONS: "1",
    RATE_LIMIT_PEPPER_V1: "automation-route-rate-limit-test",
  } as unknown as Env;
}

function appFor(identity = automationIdentity()) {
  const authenticateAutomation = vi.fn(async (_env: Env, assertion: string, requiredScope: string) => {
    expect(assertion).toBe("signed-automation-assertion");
    if (!identity.scopes.has(requiredScope)) {
      throw Object.assign(new Error("scope denied"), {
        code: "AUTOMATION_SCOPE_DENIED",
        status: 403,
      });
    }
    return identity;
  });
  const app = (createApp as unknown as (options: unknown) => ReturnType<typeof createApp>)({
    authenticateAutomation,
  });
  return { app, authenticateAutomation };
}

async function registrationPayload() {
  const manifest = "{}";
  return {
    release_id: "rel_prod_060",
    version: "0.6.0",
    channel: "stable",
    manifest_content_base64: btoa(manifest),
    manifest_signature_base64: btoa("s".repeat(64)),
    manifest_sha256: await sha256Hex(manifest),
    package_sha256: "a".repeat(64),
    package_size: 3,
    github_repository: "example/releases",
    github_release_id: "123",
    github_asset_id: "456",
    github_asset_name: "package.zip",
    distribution_backend: "github",
    operation_nonce: "nonce_register_automation_01",
  };
}

describe("release automation routes", () => {
  it("registers only through machine identity and always returns disabled/paused", async () => {
    const { app, authenticateAutomation } = appFor();
    const response = await app.request(
      "https://local.example.test/v1/automation/releases",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Cf-Access-Jwt-Assertion": "signed-automation-assertion",
        },
        body: JSON.stringify(await registrationPayload()),
      },
      env(),
    );
    expect(response.status).toBe(201);
    await expect(response.json()).resolves.toMatchObject({
      release_id: "rel_prod_060",
      enabled: false,
      paused: true,
    });
    expect(authenticateAutomation).toHaveBeenCalledWith(
      expect.anything(),
      "signed-automation-assertion",
      "releases:register",
    );
  });

  it("has no machine route for release state mutation", async () => {
    const { app } = appFor(automationIdentity(["releases:state"]));
    const response = await app.request(
      "https://local.example.test/v1/automation/releases/rel_prod_060",
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "Cf-Access-Jwt-Assertion": "signed-automation-assertion",
        },
        body: JSON.stringify({ enabled: true, operation_nonce: "nonce_state_machine_01" }),
      },
      env(),
    );
    expect(response.status).toBe(404);
  });

  it("does not accept a human wcas session as machine authentication", async () => {
    const { app, authenticateAutomation } = appFor();
    const response = await app.request(
      "https://local.example.test/v1/automation/releases",
      { headers: { Authorization: "Admin wcas_adms_abcdefghijkl." + "s".repeat(32) } },
      env(),
    );
    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toMatchObject({
      error: { code: "AUTOMATION_IDENTITY_INVALID" },
    });
    expect(authenticateAutomation).not.toHaveBeenCalled();
  });
});

describe("human-only release state boundary", () => {
  it("requires session auth mode even when another identity carries releases:state", () => {
    expect(() =>
      assertHumanReleaseStateAuthority({
        id: "human_admin",
        scopes: new Set(["releases:state"]),
        authMode: "session",
        authenticatedAt: "2026-08-15T08:00:00.000Z",
      }),
    ).not.toThrow();
    for (const authMode of ["access_service", "legacy_break_glass"] as const) {
      expect(() =>
        assertHumanReleaseStateAuthority({
          id: "not_normal_human_session",
          scopes: new Set(["releases:state"]),
          authMode,
          authenticatedAt: "2026-08-15T08:00:00.000Z",
        } as never),
      ).toThrowError(
        expect.objectContaining({
          code: "RELEASE_STATE_HUMAN_SESSION_REQUIRED",
          status: 403,
        }),
      );
    }
  });

  it("rejects legacy admin state mutation even with releases:state scope", async () => {
    const pepper = "legacy-release-state-pepper";
    const tokenId = "adm_abcdefghijkl";
    const tokenSecret = "s".repeat(32);
    const digest = await hmacSha256Hex(pepper, tokenSecret);
    const db = {
      prepare(statement: string) {
        return {
          bind() {
            return this;
          },
          async first<T>() {
            if (statement.includes("INSERT INTO rate_limit_windows")) return { count: 1 } as T;
            if (statement.includes("FROM admin_tokens")) {
              return {
                id: "admin_legacy",
                token_digest: digest,
                scopes_json: JSON.stringify(["releases:state"]),
                status: "active",
              } as T;
            }
            throw new Error(`unexpected first query: ${statement}`);
          },
          async run() {
            if (statement.includes("UPDATE admin_tokens SET last_used_at")) {
              return { success: true, meta: { changes: 1 } };
            }
            throw new Error(`unexpected run query: ${statement}`);
          },
        };
      },
    } as unknown as D1Database;
    const response = await createApp().request(
      "https://local.example.test/v1/admin/releases/rel_prod_060",
      {
        method: "PATCH",
        headers: {
          Authorization: `Admin wcadmin_${tokenId}.${tokenSecret}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ enabled: true, operation_nonce: "nonce_human_state_01" }),
      },
      {
        DB: db,
        ENVIRONMENT: "local",
        ADMIN_TOKEN_PEPPER: pepper,
        RATE_LIMIT_PEPPER_CURRENT_VERSION: "1",
        RATE_LIMIT_PEPPER_READABLE_VERSIONS: "1",
        RATE_LIMIT_PEPPER_V1: "rate-limit-release-state-test",
      } as unknown as Env,
    );
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error: { code: "RELEASE_STATE_HUMAN_SESSION_REQUIRED" },
    });
  });
});
