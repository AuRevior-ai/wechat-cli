import { describe, expect, it } from "vitest";

import { authenticateAdmin, authenticateDevice } from "../src/auth";
import { hmacSha256Hex } from "../src/crypto";
import type { Env } from "../src/types";

function authContext(env: Env, authorization: string) {
  return {
    env,
    req: {
      header(name: string) {
        return name.toLowerCase() === "authorization" ? authorization : undefined;
      },
    },
    get(name: string) {
      return name === "requestId" ? "req_version_auth" : undefined;
    },
  } as never;
}

async function versionedAuthFixture(readable = "1,2") {
  const deviceTokenId = "tk_abcdefghijklmnop";
  const deviceSecret = "d".repeat(32);
  const sessionTokenId = "adms_abcdefghijklmnop";
  const sessionSecret = "s".repeat(32);
  const deviceDigest = await hmacSha256Hex("device-old-secret-value", deviceSecret);
  const sessionDigest = await hmacSha256Hex("admin-session-old-secret-value", sessionSecret);
  const db = {
    prepare(statement: string) {
      let bindings: unknown[] = [];
      return {
        bind(...values: unknown[]) {
          bindings = values;
          return this;
        },
        async first<T>() {
          if (statement.includes("FROM devices d")) {
            if (bindings[0] !== deviceTokenId) return null as T;
            return {
              id: "device-row",
              license_id: "license-row",
              client_install_id_digest: "install-digest",
              fingerprint_digest: "fingerprint-digest",
              display_name: "Device",
              status: "active",
              token_id: deviceTokenId,
              token_secret_digest: deviceDigest,
              token_secret_version: 1,
              token_version: 1,
              device_revision: 1,
              first_activated_at: "2026-08-13T00:00:00Z",
              last_validated_at: "2026-08-13T00:00:00Z",
              last_app_version: "0.5.1",
              last_launcher_version: "0.1.0",
              disabled_at: null,
              unbound_at: null,
              license_row_id: "license-row",
              key_digest: "license-digest",
              key_secret_version: 1,
              key_hint: "ABCD",
              license_status: "active",
              max_devices: 3,
              release_channel: "stable",
              revision: 1,
              license_created_at: "2026-08-13T00:00:00Z",
              license_updated_at: "2026-08-13T00:00:00Z",
              suspended_at: null,
              revoked_at: null,
              created_by_admin_id: null,
            } as T;
          }
          if (statement.includes("FROM admin_sessions s")) {
            if (bindings[0] !== sessionTokenId) return null as T;
            return {
              id: "session-row",
              token_digest: sessionDigest,
              token_secret_version: 1,
              principal_id: "principal-row",
              scopes_json: JSON.stringify(["licenses:read"]),
              authenticated_at: new Date().toISOString(),
              expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
              status: "active",
              principal_status: "active",
            } as T;
          }
          throw new Error(`unexpected query: ${statement}`);
        },
        async run() {
          if (statement.includes("UPDATE admin_sessions SET last_used_at")) {
            return { success: true, meta: { changes: 1 } };
          }
          throw new Error(`unexpected run: ${statement}`);
        },
      };
    },
  } as unknown as D1Database;
  const env = {
    DB: db,
    ENVIRONMENT: "local",
    DEVICE_TOKEN_PEPPER_CURRENT_VERSION: "2",
    DEVICE_TOKEN_PEPPER_READABLE_VERSIONS: readable,
    DEVICE_TOKEN_PEPPER_V1: "device-old-secret-value",
    DEVICE_TOKEN_PEPPER_V2: "device-new-secret-value",
    ADMIN_SESSION_PEPPER_CURRENT_VERSION: "2",
    ADMIN_SESSION_PEPPER_READABLE_VERSIONS: readable,
    ADMIN_SESSION_PEPPER_V1: "admin-session-old-secret-value",
    ADMIN_SESSION_PEPPER_V2: "admin-session-new-secret-value",
  } as unknown as Env;
  return {
    env,
    deviceToken: `wcdt_${deviceTokenId}.${deviceSecret}`,
    sessionToken: `wcas_${sessionTokenId}.${sessionSecret}`,
  };
}

describe("stored credential secret versions", () => {
  it("authenticates old device and admin session credentials during overlap", async () => {
    const fixture = await versionedAuthFixture();
    await expect(
      authenticateDevice(authContext(fixture.env, `Bearer ${fixture.deviceToken}`)),
    ).resolves.toMatchObject({ device: { token_secret_version: 1 } });
    await expect(
      authenticateAdmin(
        authContext(fixture.env, `Admin ${fixture.sessionToken}`),
        "licenses:read",
      ),
    ).resolves.toMatchObject({ id: "principal-row", authMode: "session" });
  });

  it("invalidates old credentials immediately after version retirement", async () => {
    const fixture = await versionedAuthFixture("2");
    await expect(
      authenticateDevice(authContext(fixture.env, `Bearer ${fixture.deviceToken}`)),
    ).rejects.toMatchObject({ code: "SECRET_VERSION_NOT_READABLE" });
    await expect(
      authenticateAdmin(
        authContext(fixture.env, `Admin ${fixture.sessionToken}`),
        "licenses:read",
      ),
    ).rejects.toMatchObject({ code: "SECRET_VERSION_NOT_READABLE" });
  });
});
