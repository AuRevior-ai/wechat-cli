import { describe, expect, it, vi } from "vitest";

import { createDeviceToken, hmacSha256Hex } from "../src/crypto";
import { ApiError } from "../src/http";
import { createApp } from "../src/index";
import type { Env } from "../src/types";
import { d1BlobBytes, fetchGithubReleaseAsset } from "../src/updates";

interface FakeDbState {
  prepared: string[];
  runs: string[];
}

async function makeUpdateCheckEnv(options: {
  licensedChannel: "stable" | "beta";
  releaseChannel: "stable" | "beta";
  tokenId: string;
  tokenSecret: string;
  releaseVersion?: string | undefined;
  releaseManifestSha256?: string | undefined;
}): Promise<{ env: Env; state: FakeDbState }> {
  const state: FakeDbState = { prepared: [], runs: [] };
  const devicePepper = "device-pepper-for-update-tests";
  const tokenDigest = await hmacSha256Hex(devicePepper, options.tokenSecret);
  const authRow = {
    id: "dev_test_1",
    license_id: "lic_test_1",
    client_install_id_digest: "install-digest",
    fingerprint_digest: "fingerprint-digest",
    display_name: "test-device",
    status: "active",
    token_id: options.tokenId,
    token_secret_digest: tokenDigest,
    token_version: 1,
    device_revision: 1,
    first_activated_at: "2026-08-12T00:00:00.000Z",
    last_validated_at: "2026-08-12T00:00:00.000Z",
    last_app_version: "0.5.0",
    last_launcher_version: "0.1.0",
    disabled_at: null,
    unbound_at: null,
    license_row_id: "lic_test_1",
    key_digest: "license-digest",
    key_hint: "TEST",
    license_status: "active",
    max_devices: 1,
    release_channel: options.licensedChannel,
    revision: 1,
    license_created_at: "2026-08-12T00:00:00.000Z",
    license_updated_at: "2026-08-12T00:00:00.000Z",
    suspended_at: null,
    revoked_at: null,
    created_by_admin_id: null,
  };
  const releaseRow = {
    id: "rel_test_beta",
    version: options.releaseVersion ?? "0.6.0",
    channel: options.releaseChannel,
    manifest_content: [123, 125],
    manifest_signature: [1, 2, 3],
    manifest_sha256: options.releaseManifestSha256 ?? "a".repeat(64),
    package_sha256: "b".repeat(64),
    package_size: 1234,
    github_repository: "org/repo",
    github_release_id: "123",
    github_asset_id: "456",
    github_asset_name: "package.zip",
    rollout_percentage: 100,
    rollout_seed: "seed",
    paused: 0,
    enabled: 1,
    published_at: "2026-08-12T00:00:00.000Z",
    created_at: "2026-08-12T00:00:00.000Z",
  };

  const db = {
    prepare(sql: string) {
      state.prepared.push(sql);
      let bindings: unknown[] = [];
      return {
        bind(...values: unknown[]) {
          bindings = values;
          return this;
        },
        async first<T>() {
          if (sql.includes("FROM devices d")) {
            return authRow as T;
          }
          if (sql.includes("INSERT INTO rate_limit_windows")) {
            return { count: 1 } as T;
          }
          throw new Error(`unexpected first(): ${sql} ${JSON.stringify(bindings)}`);
        },
        async all<T>() {
          if (sql.includes("FROM releases")) {
            return {
              results: [releaseRow as T],
              success: true,
              meta: {},
            };
          }
          throw new Error(`unexpected all(): ${sql} ${JSON.stringify(bindings)}`);
        },
        async run() {
          state.runs.push(sql);
          return { success: true, meta: { changes: 1 } };
        },
      };
    },
  } as unknown as D1Database;

  return {
    env: {
      DB: db,
      DIAGNOSTICS: {} as R2Bucket,
      RELEASES: {} as R2Bucket,
      ENVIRONMENT: "local",
      LEASE_SIGNING_KEY_ID: "lease-test",
      CONTACT_ENCRYPTION_KEY_VERSION: "1",
      MAX_DIAGNOSTIC_BYTES: "1024",
      LICENSE_KEY_PEPPER: "license-pepper-for-tests",
      DEVICE_TOKEN_PEPPER: devicePepper,
      RATE_LIMIT_PEPPER: "rate-limit-pepper-update-tests",
      ADMIN_TOKEN_PEPPER: "admin-pepper-for-tests",
      CONTACT_LOOKUP_PEPPER: "contact-pepper-for-tests",
      CONTACT_ENCRYPTION_KEY_V1: "contact-encryption-key-for-tests",
      LEASE_SIGNING_PRIVATE_KEY: "lease-private-key-for-tests",
      DOWNLOAD_TICKET_SECRET: "download-ticket-secret-for-tests",
      GITHUB_RELEASE_READ_TOKEN: "github-test-token",
    },
    state,
  };
}

async function updateCheck(options: {
  licensedChannel: "stable" | "beta";
  requestedChannel: "stable" | "beta";
  failedVersions?: string[];
  failedReleases?: Array<{ version: string; manifest_sha256: string }>;
  releaseVersion?: string;
  releaseManifestSha256?: string;
}): Promise<{ response: Response; state: FakeDbState }> {
  const token = createDeviceToken();
  const { env, state } = await makeUpdateCheckEnv({
    licensedChannel: options.licensedChannel,
    releaseChannel: options.requestedChannel,
    tokenId: token.tokenId,
    tokenSecret: token.tokenSecret,
    releaseVersion: options.releaseVersion,
    releaseManifestSha256: options.releaseManifestSha256,
  });
  const response = await createApp().request(
    "/v1/updates/check",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token.value}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        current_version: "0.5.0",
        launcher_version: "0.1.0",
        channel: options.requestedChannel,
        platform: "windows",
        architecture: "x86_64",
        product: "wechat-cli-web",
        device_id: "dev_test_1",
        failed_versions: options.failedVersions ?? [],
        failed_releases: options.failedReleases ?? [],
      }),
    },
    env,
  );
  return { response, state };
}

describe("update channel authorization", () => {
  it("rejects a stable license requesting beta before release selection or ticket creation", async () => {
    const { response, state } = await updateCheck({
      licensedChannel: "stable",
      requestedChannel: "beta",
    });

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      error: { code: "UPDATE_CHANNEL_MISMATCH", retryable: false },
    });
    expect(state.prepared.some((sql) => sql.includes("FROM releases"))).toBe(false);
    expect(state.runs.some((sql) => sql.includes("INSERT INTO download_tickets"))).toBe(false);
  });

  it("rejects a beta license requesting stable before release selection or ticket creation", async () => {
    const { response, state } = await updateCheck({
      licensedChannel: "beta",
      requestedChannel: "stable",
    });

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      error: { code: "UPDATE_CHANNEL_MISMATCH", retryable: false },
    });
    expect(state.prepared.some((sql) => sql.includes("FROM releases"))).toBe(false);
    expect(state.runs.some((sql) => sql.includes("INSERT INTO download_tickets"))).toBe(false);
  });

  it("uses the authenticated license channel when request and license agree", async () => {
    const { response, state } = await updateCheck({
      licensedChannel: "stable",
      requestedChannel: "stable",
    });

    expect(response.status).toBe(200);
    expect(state.prepared.some((sql) => sql.includes("FROM releases"))).toBe(true);
    expect(state.runs.some((sql) => sql.includes("INSERT INTO download_tickets"))).toBe(true);
  });
});

describe("exact failed release suppression", () => {
  it("suppresses the exact failed version and manifest pair", async () => {
    const manifestSha = "a".repeat(64);
    const { response, state } = await updateCheck({
      licensedChannel: "stable",
      requestedChannel: "stable",
      failedReleases: [{ version: "0.6.0", manifest_sha256: manifestSha }],
      releaseVersion: "0.6.0",
      releaseManifestSha256: manifestSha,
    });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ update_available: false });
    expect(state.runs.some((sql) => sql.includes("INSERT INTO download_tickets"))).toBe(false);
  });

  it("does not suppress the same version when the manifest differs", async () => {
    const { response, state } = await updateCheck({
      licensedChannel: "stable",
      requestedChannel: "stable",
      failedReleases: [{ version: "0.6.0", manifest_sha256: "c".repeat(64) }],
      releaseVersion: "0.6.0",
      releaseManifestSha256: "a".repeat(64),
    });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ update_available: true });
    expect(state.runs.some((sql) => sql.includes("INSERT INTO download_tickets"))).toBe(true);
  });

  it("keeps legacy failed_versions suppression for old clients", async () => {
    const { response, state } = await updateCheck({
      licensedChannel: "stable",
      requestedChannel: "stable",
      failedVersions: ["0.6.0"],
    });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ update_available: false });
    expect(state.runs.some((sql) => sql.includes("INSERT INTO download_tickets"))).toBe(false);
  });

  it("rejects malformed failed release hashes", async () => {
    const { response } = await updateCheck({
      licensedChannel: "stable",
      requestedChannel: "stable",
      failedReleases: [{ version: "0.6.0", manifest_sha256: "bad" }],
    });

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({ error: { code: "INVALID_REQUEST" } });
  });

  it("rejects more than 32 exact failed releases", async () => {
    const { response } = await updateCheck({
      licensedChannel: "stable",
      requestedChannel: "stable",
      failedReleases: Array.from({ length: 33 }, (_, index) => ({
        version: `0.6.${index}`,
        manifest_sha256: "d".repeat(64),
      })),
    });

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({ error: { code: "INVALID_REQUEST" } });
  });
});

describe("D1 BLOB decoding", () => {
  it("accepts ArrayBuffer and typed-array values", () => {
    const buffer = Uint8Array.from([1, 2, 3]).buffer;
    expect([...d1BlobBytes(buffer, "manifest")]).toEqual([1, 2, 3]);
    expect([...d1BlobBytes(Uint8Array.from([4, 5]), "signature")]).toEqual([
      4,
      5,
    ]);
  });

  it("accepts the plain byte arrays returned by local D1", () => {
    expect([...d1BlobBytes([0, 127, 255], "manifest")]).toEqual([
      0,
      127,
      255,
    ]);
  });

  it("rejects strings and out-of-range array values", () => {
    for (const value of ["AQID", [0, 256], [1, -1], [1, 1.5]]) {
      try {
        d1BlobBytes(value, "manifest");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).code).toBe("RELEASE_STATE_INVALID");
        continue;
      }
      throw new Error("invalid D1 BLOB value was accepted");
    }
  });
});

describe("GitHub release asset fetch", () => {
  it("follows HTTPS redirects manually without forwarding authorization", async () => {
    const calls: Array<{
      url: string;
      headers: Headers;
      redirect: RequestRedirect | undefined;
    }> = [];
    const fakeFetch = async (
      input: RequestInfo | URL,
      init?: RequestInit,
    ): Promise<Response> => {
      const url = String(input);
      calls.push({
        url,
        headers: new Headers(init?.headers),
        redirect: init?.redirect,
      });
      if (calls.length === 1) {
        return new Response(null, {
          status: 302,
          headers: {
            Location: "https://objects.githubusercontent.com/private-asset",
          },
        });
      }
      return new Response(new Uint8Array([1]), {
        status: 206,
        headers: { "Content-Range": "bytes 0-0/1" },
      });
    };
    const headers = new Headers({
      Accept: "application/octet-stream",
      Authorization: "Bearer github-secret",
      Range: "bytes=0-0",
      "User-Agent": "wechat-cli-license-update-worker",
    });

    const response = await fetchGithubReleaseAsset(
      "https://api.github.com/repos/org/repo/releases/assets/123",
      headers,
      fakeFetch as typeof fetch,
    );

    expect(response.status).toBe(206);
    expect(calls).toHaveLength(2);
    expect(calls[0]?.redirect).toBe("manual");
    expect(calls[0]?.headers.get("Authorization")).toBe("Bearer github-secret");
    expect(calls[1]?.url).toBe(
      "https://objects.githubusercontent.com/private-asset",
    );
    expect(calls[1]?.headers.get("Authorization")).toBeNull();
    expect(calls[1]?.headers.get("Range")).toBe("bytes=0-0");
  });

  it("rejects non-HTTPS GitHub asset redirects", async () => {
    const fakeFetch = async (): Promise<Response> =>
      new Response(null, {
        status: 302,
        headers: { Location: "http://example.invalid/private-asset" },
      });

    await expect(
      fetchGithubReleaseAsset(
        "https://api.github.com/repos/org/repo/releases/assets/123",
        new Headers({ Authorization: "Bearer github-secret" }),
        fakeFetch as typeof fetch,
      ),
    ).rejects.toMatchObject({ code: "DOWNLOAD_UPSTREAM_FAILED" });
  });

  it("reports only the safe final upstream status on GitHub failure", async () => {
    const fakeFetch = async (): Promise<Response> =>
      new Response(null, { status: 403 });
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => undefined);

    try {
      await expect(
        fetchGithubReleaseAsset(
          "https://api.github.com/repos/org/repo/releases/assets/123",
          new Headers({ Authorization: "Bearer TEST_VALUE" }),
          fakeFetch as typeof fetch,
        ),
      ).rejects.toMatchObject({
        code: "DOWNLOAD_UPSTREAM_FAILED",
        status: 502,
        retryable: false,
        details: { upstream_status: 403 },
      });
      const logged = errorLog.mock.calls.flat().join(" ");
      expect(logged).toContain("github_release_asset_upstream_failed");
      expect(logged).toContain('"upstream_status":403');
      expect(logged).not.toContain("TEST_VALUE");
    } finally {
      errorLog.mockRestore();
    }
  });

  it("fails closed after a bounded number of redirects", async () => {
    let calls = 0;
    const fakeFetch = async (): Promise<Response> => {
      calls += 1;
      if (calls <= 5) {
        return new Response(null, {
          status: 302,
          headers: { Location: `https://example.invalid/hop-${calls}` },
        });
      }
      return new Response(new Uint8Array([1]), { status: 200 });
    };

    await expect(
      fetchGithubReleaseAsset(
        "https://api.github.com/repos/org/repo/releases/assets/123",
        new Headers({ Authorization: "Bearer github-secret" }),
        fakeFetch as typeof fetch,
      ),
    ).rejects.toMatchObject({ code: "DOWNLOAD_UPSTREAM_FAILED" });
    expect(calls).toBeLessThanOrEqual(4);
  });
});
