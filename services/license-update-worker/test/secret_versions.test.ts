import { describe, expect, it } from "vitest";

import { hmacSha256Hex } from "../src/crypto";
import type { Env } from "../src/types";

type SecretVersionsModule = {
  versionedSecretSet?: (
    env: Env,
    purpose:
      | "license-key-pepper"
      | "device-token-pepper"
      | "admin-session-pepper"
      | "contact-lookup-pepper"
      | "download-ticket-secret"
      | "diagnostic-upload-secret"
      | "rate-limit-pepper",
  ) => {
    currentVersion: number;
    readableVersions: number[];
    value(version: number): string;
    current(): { version: number; value: string };
  };
  versionedHmacDigest?: (
    env: Env,
    purpose:
      | "license-key-pepper"
      | "device-token-pepper"
      | "admin-session-pepper"
      | "contact-lookup-pepper"
      | "download-ticket-secret"
      | "diagnostic-upload-secret"
      | "rate-limit-pepper",
    message: string,
  ) => Promise<{ version: number; digest: string }>;
  verifyVersionedHmacDigest?: (
    env: Env,
    purpose:
      | "license-key-pepper"
      | "device-token-pepper"
      | "admin-session-pepper"
      | "contact-lookup-pepper"
      | "download-ticket-secret"
      | "diagnostic-upload-secret"
      | "rate-limit-pepper",
    version: number,
    message: string,
    expectedDigest: string,
  ) => Promise<boolean>;
};

async function moduleContract(): Promise<Required<SecretVersionsModule>> {
  const path = "../src/secret_versions";
  let module: SecretVersionsModule = {};
  try {
    module = (await import(path)) as SecretVersionsModule;
  } catch {
    module = {};
  }
  expect(module.versionedSecretSet).toBeTypeOf("function");
  expect(module.versionedHmacDigest).toBeTypeOf("function");
  expect(module.verifyVersionedHmacDigest).toBeTypeOf("function");
  return module as Required<SecretVersionsModule>;
}

function envFor(prefix: string, options?: { current?: string; readable?: string }) {
  return {
    [`${prefix}_CURRENT_VERSION`]: options?.current ?? "2",
    [`${prefix}_READABLE_VERSIONS`]: options?.readable ?? "1,2",
    [`${prefix}_V1`]: `${prefix.toLowerCase()}-old-secret-value`,
    [`${prefix}_V2`]: `${prefix.toLowerCase()}-new-secret-value`,
  } as unknown as Env;
}

describe("versioned secret provider", () => {
  it("uses current for new writes while old and new remain readable during overlap", async () => {
    const module = await moduleContract();
    const env = envFor("DEVICE_TOKEN_PEPPER");
    const set = module.versionedSecretSet(env, "device-token-pepper");

    expect(set.currentVersion).toBe(2);
    expect(set.readableVersions).toEqual([1, 2]);
    expect(set.current().version).toBe(2);
    const written = await module.versionedHmacDigest(
      env,
      "device-token-pepper",
      "device-secret",
    );
    expect(written.version).toBe(2);
    expect(written.digest).toBe(
      await hmacSha256Hex(set.value(2), "device-secret"),
    );
    const oldDigest = await hmacSha256Hex(set.value(1), "device-secret");
    await expect(
      module.verifyVersionedHmacDigest(
        env,
        "device-token-pepper",
        1,
        "device-secret",
        oldDigest,
      ),
    ).resolves.toBe(true);
  });

  it("retires an old version immediately by removing it from readableVersions", async () => {
    const module = await moduleContract();
    const env = envFor("ADMIN_SESSION_PEPPER", { readable: "2" });
    const oldDigest = await hmacSha256Hex(
      "admin_session_pepper-old-secret-value",
      "session-secret",
    );

    await expect(
      module.verifyVersionedHmacDigest(
        env,
        "admin-session-pepper",
        1,
        "session-secret",
        oldDigest,
      ),
    ).rejects.toMatchObject({ code: "SECRET_VERSION_NOT_READABLE" });
  });

  it("keeps download-ticket and diagnostic-upload purposes cryptographically separate", async () => {
    const module = await moduleContract();
    const env = {
      ...envFor("DOWNLOAD_TICKET_SECRET", { current: "1", readable: "1" }),
      ...envFor("DIAGNOSTIC_UPLOAD_SECRET", { current: "1", readable: "1" }),
    } as Env;
    const download = await module.versionedHmacDigest(
      env,
      "download-ticket-secret",
      "same-message",
    );
    const diagnostic = await module.versionedHmacDigest(
      env,
      "diagnostic-upload-secret",
      "same-message",
    );

    expect(download.digest).not.toBe(diagnostic.digest);
    await expect(
      module.verifyVersionedHmacDigest(
        env,
        "diagnostic-upload-secret",
        download.version,
        "same-message",
        download.digest,
      ),
    ).resolves.toBe(false);
  });

  it.each([
    ["duplicate readable versions", { current: "2", readable: "1,2,2" }],
    ["current not readable", { current: "2", readable: "1" }],
    ["invalid current", { current: "0", readable: "1" }],
    ["unbounded readable set", { current: "1", readable: "1,2,3,4,5,6,7,8,9" }],
  ])("rejects %s", async (_name, options) => {
    const module = await moduleContract();
    expect(() =>
      module.versionedSecretSet(
        envFor("LICENSE_KEY_PEPPER", options),
        "license-key-pepper",
      ),
    ).toThrow();
  });

  it("rejects a configured readable version whose value is missing or empty", async () => {
    const module = await moduleContract();
    const env = envFor("RATE_LIMIT_PEPPER") as unknown as Record<string, unknown>;
    env.RATE_LIMIT_PEPPER_V1 = "";
    expect(() =>
      module.versionedSecretSet(env as unknown as Env, "rate-limit-pepper"),
    ).toThrow();
  });
});
