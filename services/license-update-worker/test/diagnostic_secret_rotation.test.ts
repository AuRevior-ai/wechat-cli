import { describe, expect, it } from "vitest";

import { hmacSha256Hex } from "../src/crypto";
import type { Env } from "../src/types";

type DiagnosticsModule = {
  createUploadToken?: (
    env: Env,
    sessionId: string,
    expiresAtEpoch: number,
  ) => Promise<string>;
  verifyUploadToken?: (
    env: Env,
    sessionId: string,
    token: string,
  ) => Promise<void>;
};

async function contract(): Promise<Required<DiagnosticsModule>> {
  const module = (await import("../src/diagnostics")) as DiagnosticsModule;
  expect(module.createUploadToken).toBeTypeOf("function");
  expect(module.verifyUploadToken).toBeTypeOf("function");
  return module as Required<DiagnosticsModule>;
}

function env(readable = "1,2"): Env {
  return {
    DIAGNOSTIC_UPLOAD_SECRET_CURRENT_VERSION: "2",
    DIAGNOSTIC_UPLOAD_SECRET_READABLE_VERSIONS: readable,
    DIAGNOSTIC_UPLOAD_SECRET_V1: "diagnostic-old-secret-value",
    DIAGNOSTIC_UPLOAD_SECRET_V2: "diagnostic-new-secret-value",
    DOWNLOAD_TICKET_SECRET_CURRENT_VERSION: "1",
    DOWNLOAD_TICKET_SECRET_READABLE_VERSIONS: "1",
    DOWNLOAD_TICKET_SECRET_V1: "download-secret-different-value",
  } as unknown as Env;
}

describe("diagnostic upload secret rotation", () => {
  it("new tokens encode the current diagnostic secret version", async () => {
    const module = await contract();
    const token = await module.createUploadToken(env(), "diag_session_123456", 2_000_000_000);
    expect(token).toMatch(/^diag_v2_2000000000\./u);
    await expect(
      module.verifyUploadToken(env(), "diag_session_123456", token),
    ).resolves.toBeUndefined();
  });

  it("accepts an old diagnostic version during overlap and rejects it immediately after retirement", async () => {
    const module = await contract();
    const sessionId = "diag_session_123456";
    const expiresAt = 2_000_000_000;
    const nonce = "abcdefghijklmnopqrstuvwx";
    const message = `${sessionId}\u0000${expiresAt}\u0000${nonce}`;
    const signature = await hmacSha256Hex("diagnostic-old-secret-value", message);
    const token = `diag_v1_${expiresAt}.${nonce}.${signature}`;

    await expect(module.verifyUploadToken(env(), sessionId, token)).resolves.toBeUndefined();
    await expect(
      module.verifyUploadToken(env("2"), sessionId, token),
    ).rejects.toMatchObject({ code: "SECRET_VERSION_NOT_READABLE" });
  });

  it("never accepts a token signed with the download-ticket secret", async () => {
    const module = await contract();
    const sessionId = "diag_session_123456";
    const expiresAt = 2_000_000_000;
    const nonce = "abcdefghijklmnopqrstuvwx";
    const message = `${sessionId}\u0000${expiresAt}\u0000${nonce}`;
    const signature = await hmacSha256Hex("download-secret-different-value", message);
    const token = `diag_v1_${expiresAt}.${nonce}.${signature}`;

    await expect(
      module.verifyUploadToken(env(), sessionId, token),
    ).rejects.toMatchObject({ code: "DIAGNOSTIC_UPLOAD_NOT_AUTHORIZED" });
  });
});
