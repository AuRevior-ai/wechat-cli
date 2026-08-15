import { describe, expect, it, vi } from "vitest";

import type { Env } from "../src/types";

type DiagnosticsModule = {
  diagnosticDeadlines?: (now: Date) => {
    upload_expires_at: string;
    retention_expires_at: string;
  };
  diagnosticObjectKey?: (now: Date, submissionId: string) => string;
  validateDiagnosticConsent?: (value: unknown) => string;
  putDiagnosticObject?: (
    env: Env,
    options: {
      objectKey: string;
      content: ArrayBuffer;
      submissionId: string;
      sha256: string;
    },
  ) => Promise<void>;
  cleanupExpiredDiagnostics?: (env: Env, now?: Date) => Promise<void>;
};

async function diagnosticsModule(): Promise<Required<DiagnosticsModule>> {
  const module = (await import("../src/diagnostics")) as DiagnosticsModule;
  expect(module.diagnosticDeadlines).toBeTypeOf("function");
  expect(module.diagnosticObjectKey).toBeTypeOf("function");
  expect(module.validateDiagnosticConsent).toBeTypeOf("function");
  expect(module.putDiagnosticObject).toBeTypeOf("function");
  expect(module.cleanupExpiredDiagnostics).toBeTypeOf("function");
  return module as Required<DiagnosticsModule>;
}

describe("diagnostic retention policy", () => {
  it("separates a 15 minute upload TTL from a 7 day retention TTL", async () => {
    const module = await diagnosticsModule();
    expect(module.diagnosticDeadlines(new Date("2026-08-13T00:00:00Z"))).toEqual({
      upload_expires_at: "2026-08-13T00:15:00.000Z",
      retention_expires_at: "2026-08-20T00:00:00.000Z",
    });
  });

  it("uses an opaque object key without license or device identifiers", async () => {
    const module = await diagnosticsModule();
    const key = module.diagnosticObjectKey(
      new Date("2026-08-13T00:00:00Z"),
      "diag_abcdefghijklmnop",
    );
    expect(key).toBe("diagnostics/2026-08-13/diag_abcdefghijklmnop.zip");
    expect(key).not.toContain("lic_");
    expect(key).not.toContain("dev_");
  });

  it("requires the exact consent contract version", async () => {
    const module = await diagnosticsModule();
    expect(module.validateDiagnosticConsent("diagnostics-consent-v1")).toBe(
      "diagnostics-consent-v1",
    );
    for (const value of [undefined, null, "", "diagnostics-consent-v0", 1]) {
      expect(() => module.validateDiagnosticConsent(value)).toThrow();
    }
  });

  it("writes only submission id and sha256 as R2 custom metadata", async () => {
    const module = await diagnosticsModule();
    const put = vi.fn(
      async (
        _key: string,
        _value: ArrayBuffer,
        _options?: R2PutOptions,
      ) => ({}) as R2Object,
    );
    const env = { DIAGNOSTICS: { put } as unknown as R2Bucket } as Env;
    const content = Uint8Array.from([1, 2, 3]).buffer;
    await module.putDiagnosticObject(env, {
      objectKey: "diagnostics/2026-08-13/diag_abcdefghijklmnop.zip",
      content,
      submissionId: "diag_abcdefghijklmnop",
      sha256: "a".repeat(64),
    });

    expect(put).toHaveBeenCalledTimes(1);
    const options = put.mock.calls[0]?.[2] as R2PutOptions;
    expect(options.customMetadata).toEqual({
      submission_id: "diag_abcdefghijklmnop",
      sha256: "a".repeat(64),
    });
    expect(JSON.stringify(options.customMetadata)).not.toContain("license");
    expect(JSON.stringify(options.customMetadata)).not.toContain("device");
  });

  it("cleanup deletes cloud content only after retention expiry, not upload expiry", async () => {
    const module = await diagnosticsModule();
    const deleteObject = vi.fn(async () => undefined);
    const updated: string[] = [];
    const rows = [
      {
        id: "diag_retained",
        object_key: "diagnostics/2026-08-13/diag_retained.zip",
        status: "complete",
      },
    ];
    const db = {
      prepare(statement: string) {
        let bindings: unknown[] = [];
        return {
          bind(...values: unknown[]) {
            bindings = values;
            return this;
          },
          async all<T>() {
            expect(statement).toContain("retention_expires_at <= ?");
            expect(bindings[0]).toBe("2026-08-20T00:00:00.000Z");
            return { results: rows as T[] };
          },
          async run() {
            if (statement.includes("UPDATE diagnostic_submissions")) {
              updated.push(String(bindings[0]));
            }
            return { success: true, meta: { changes: 1 } };
          },
        };
      },
    } as unknown as D1Database;
    const env = {
      DB: db,
      DIAGNOSTICS: { delete: deleteObject } as unknown as R2Bucket,
    } as Env;

    await module.cleanupExpiredDiagnostics(
      env,
      new Date("2026-08-20T00:00:00Z"),
    );

    expect(deleteObject).toHaveBeenCalledWith(
      "diagnostics/2026-08-13/diag_retained.zip",
    );
    expect(updated).toEqual(["diag_retained"]);
  });
});
