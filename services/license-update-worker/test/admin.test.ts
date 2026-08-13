import { describe, expect, it, vi } from "vitest";

import * as adminModule from "../src/admin";
import { hmacSha256Hex, sha256Hex } from "../src/crypto";
import { ApiError } from "../src/http";
import { createApp } from "../src/index";
import type { Env } from "../src/types";

interface QueryState {
  sql: string[];
  bindings: unknown[][];
}

function releaseLookupEnv(existingManifestSha256: string | null): {
  env: Env;
  state: QueryState;
} {
  const state: QueryState = { sql: [], bindings: [] };
  const db = {
    prepare(sql: string) {
      state.sql.push(sql);
      let bound: unknown[] = [];
      return {
        bind(...values: unknown[]) {
          bound = values;
          state.bindings.push(values);
          return this;
        },
        async first<T>() {
          if (!sql.includes("FROM releases")) {
            throw new Error(`unexpected query: ${sql}`);
          }
          if (existingManifestSha256 === null) {
            return null;
          }
          return {
            id: "rel_existing",
            manifest_sha256: existingManifestSha256,
          } as T;
        },
      };
    },
  } as unknown as D1Database;
  return { env: { DB: db } as Env, state };
}

async function adminRouteEnv(options?: {
  releaseRow?: Record<string, unknown> | null;
}): Promise<{
  env: Env;
  token: string;
  sql: string[];
  runs: string[];
  r2Put: ReturnType<typeof vi.fn>;
}> {
  const adminPepper = "admin-pepper-route-test";
  const tokenId = "adm_abcdefghijkl";
  const tokenSecret = "s".repeat(32);
  const token = `wcadmin_${tokenId}.${tokenSecret}`;
  const tokenDigest = await hmacSha256Hex(adminPepper, tokenSecret);
  const sql: string[] = [];
  const runs: string[] = [];
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
          if (statement.includes("INSERT INTO rate_limit_windows")) {
            return { count: 1 } as T;
          }
          if (statement.includes("FROM admin_tokens")) {
            return {
              id: "admin_test",
              token_digest: tokenDigest,
              scopes_json: JSON.stringify(["releases:upload", "releases:write"]),
              status: "active",
            } as T;
          }
          if (statement.includes("FROM releases") && options?.releaseRow !== undefined) {
            return (options.releaseRow ?? null) as T;
          }
          throw new Error(`unexpected first(): ${statement} ${JSON.stringify(bindings)}`);
        },
        async run() {
          runs.push(statement);
          return { success: true, meta: { changes: 1 } };
        },
      };
    },
  } as unknown as D1Database;

  let stored: R2Object | null = null;
  const r2Put = vi.fn(async (key: string, value: ArrayBuffer, putOptions?: R2PutOptions) => {
    stored = {
      key,
      version: "v1",
      size: value.byteLength,
      etag: "etag",
      httpEtag: '"etag"',
      checksums: {} as R2Checksums,
      uploaded: new Date("2026-08-12T00:00:00Z"),
      customMetadata: putOptions?.customMetadata,
      storageClass: "Standard",
      writeHttpMetadata() {},
    } as R2Object;
    return stored;
  });
  const releases = {
    async head() {
      return stored;
    },
    put: r2Put,
  } as unknown as R2Bucket;

  return {
    env: {
      DB: db,
      RELEASES: releases,
      ENVIRONMENT: "local",
      ADMIN_TOKEN_PEPPER: adminPepper,
      RATE_LIMIT_PEPPER: "rate-limit-pepper-admin-tests",
    } as Env,
    token,
    sql,
    runs,
    r2Put,
  };
}

function immutabilityAssertion(): (
  env: Env,
  channel: "stable" | "beta",
  version: string,
  manifestSha256: string,
) => Promise<void> {
  const candidate = (
    adminModule as unknown as {
      assertReleaseVersionImmutable?: (
        env: Env,
        channel: "stable" | "beta",
        version: string,
        manifestSha256: string,
      ) => Promise<void>;
    }
  ).assertReleaseVersionImmutable;
  expect(candidate).toBeTypeOf("function");
  return candidate as NonNullable<typeof candidate>;
}

describe("R2 release administration", () => {
  it("uploads exact package bytes under a server-generated R2 key", async () => {
    const { env, token, r2Put } = await adminRouteEnv();
    const bytes = Uint8Array.from([1, 2, 3]);
    const packageSha256 = await sha256Hex(bytes);
    const response = await createApp().request(
      "/v1/admin/releases/rel_051/package",
      {
        method: "PUT",
        headers: {
          Authorization: `Admin ${token}`,
          "Content-Type": "application/zip",
          "Content-Length": "3",
          "X-Release-Channel": "stable",
          "X-Package-Sha256": packageSha256,
          "X-Operation-Nonce": "nonce_upload_01",
        },
        body: bytes,
      },
      env,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      release_id: "rel_051",
      distribution_backend: "r2",
      distribution_object_key: `releases/stable/rel_051/${packageSha256}.zip`,
      package_sha256: packageSha256,
      package_size: 3,
      ready: true,
    });
    expect(r2Put).toHaveBeenCalledTimes(1);
  });

  it("refuses R2 release registration until the exact object is ready", async () => {
    const { env, token, sql } = await adminRouteEnv();
    const manifest = "{}";
    const manifestSha256 = await sha256Hex(manifest);
    const packageSha256 = "a".repeat(64);
    const response = await createApp().request(
      "/v1/admin/releases",
      {
        method: "POST",
        headers: {
          Authorization: `Admin ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          release_id: "rel_051",
          version: "0.5.1",
          channel: "stable",
          manifest_content_base64: btoa(manifest),
          manifest_signature_base64: btoa("s".repeat(64)),
          manifest_sha256: manifestSha256,
          package_sha256: packageSha256,
          package_size: 3,
          github_repository: "org/repo",
          github_release_id: "123",
          github_asset_id: "456",
          github_asset_name: "package.zip",
          distribution_backend: "r2",
          distribution_object_key: `releases/stable/rel_051/${packageSha256}.zip`,
          operation_nonce: "nonce_register_01",
        }),
      },
      env,
    );

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toMatchObject({
      error: { code: "RELEASE_STATE_INVALID" },
    });
    expect(sql.some((statement) => statement.includes("INSERT INTO releases"))).toBe(false);
  });
});

describe("diagnostic admin metadata", () => {
  it("exposes retention policy fields for read-only audit", () => {
    const serializer = (
      adminModule as unknown as {
        diagnosticAdminRecord?: (row: Record<string, unknown>) => Record<string, unknown>;
      }
    ).diagnosticAdminRecord;
    expect(serializer).toBeTypeOf("function");
    expect(
      serializer!({
        id: "diagnostic-sample",
        license_id: "sample-license",
        device_id: "sample-device",
        size: 3,
        sha256: "a".repeat(64),
        client_version: "0.5.1",
        launcher_version: "0.1.0",
        status: "complete",
        submitted_at: "2026-08-13T00:05:00Z",
        upload_expires_at: "2026-08-13T00:15:00Z",
        retention_expires_at: "2026-08-20T00:00:00Z",
        consent_version: "diagnostics-consent-v1",
        downloaded_at: null,
        created_at: "2026-08-13T00:00:00Z",
      }),
    ).toMatchObject({
      submission_id: "diagnostic-sample",
      upload_expires_at: "2026-08-13T00:15:00Z",
      retention_expires_at: "2026-08-20T00:00:00Z",
      retention_days: 7,
      consent_version: "diagnostics-consent-v1",
    });
  });
});

describe("release version immutability", () => {
  it("rejects the same channel and version with a different manifest", async () => {
    const { env, state } = releaseLookupEnv("a".repeat(64));
    const assertImmutable = immutabilityAssertion();

    await expect(
      assertImmutable(env, "stable", "0.6.0", "b".repeat(64)),
    ).rejects.toMatchObject({
      code: "RELEASE_VERSION_IMMUTABLE",
      status: 409,
    } satisfies Partial<ApiError>);
    expect(state.sql).toHaveLength(1);
    expect(state.bindings[0]).toEqual(["stable", "0.6.0"]);
  });

  it("allows an exact-manifest replay or a previously unused version", async () => {
    const exact = releaseLookupEnv("a".repeat(64));
    const absent = releaseLookupEnv(null);
    const assertImmutable = immutabilityAssertion();

    await expect(
      assertImmutable(exact.env, "stable", "0.6.0", "a".repeat(64)),
    ).resolves.toBeUndefined();
    await expect(
      assertImmutable(absent.env, "beta", "0.7.0", "c".repeat(64)),
    ).resolves.toBeUndefined();
  });
});
