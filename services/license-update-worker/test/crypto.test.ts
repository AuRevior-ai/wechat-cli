import { describe, expect, it } from "vitest";

import {
  base64ToBytes,
  bytesToBase64,
  constantTimeEqual,
  createDeviceToken,
  createLicenseKey,
  deriveLicenseKey,
  deriveOpaqueId,
  decryptContacts,
  encryptContacts,
  hmacSha256Hex,
  licenseKeyHint,
  normalizeLicenseKey,
  parseDeviceToken,
  rolloutBucket,
  sha256Hex,
} from "../src/crypto";

const CONTACT_KEY = bytesToBase64(
  Uint8Array.from({ length: 32 }, (_value, index) => index),
);

describe("license key normalization", () => {
  it("creates permanent keys in the public display format", () => {
    const first = createLicenseKey();
    const second = createLicenseKey();
    expect(first).toMatch(/^WCL(?:-[A-Z2-9]{4}){4}$/u);
    expect(second).toMatch(/^WCL(?:-[A-Z2-9]{4}){4}$/u);
    expect(first === second).toBe(false);
    expect(normalizeLicenseKey(first)).toHaveLength(19);
  });

  it("derives retry-safe keys and opaque IDs without storing plaintext", async () => {
    const first = await deriveLicenseKey(
      "generation-secret-at-least-16",
      "admin-01\u0000request-01\u00000",
    );
    const retry = await deriveLicenseKey(
      "generation-secret-at-least-16",
      "admin-01\u0000request-01\u00000",
    );
    const next = await deriveLicenseKey(
      "generation-secret-at-least-16",
      "admin-01\u0000request-01\u00001",
    );
    expect(first).toBe(retry);
    expect(first === next).toBe(false);
    expect(first).toMatch(/^WCL(?:-[A-Z2-9]{4}){4}$/u);

    const id = await deriveOpaqueId(
      "lic_",
      "generation-secret-at-least-16",
      "admin-01\u0000request-01\u00000",
    );
    expect(id).toMatch(/^lic_[A-Za-z0-9_-]+$/u);
    expect(
      id ===
        (await deriveOpaqueId(
          "lic_",
          "generation-secret-at-least-16",
          "admin-01\u0000request-01\u00000",
        )),
    ).toBe(true);
  });

  it("normalizes separators and preserves only the lookup form", () => {
    expect(normalizeLicenseKey(" wcl-abcd-efgh-ijkl-mnop ")).toBe(
      "WCLABCDEFGHIJKLMNOP",
    );
    expect(licenseKeyHint("wcl-abcd-efgh-ijkl-mnop")).toBe("MNOP");
  });

  it("rejects malformed keys", () => {
    expect(() => normalizeLicenseKey("not-a-license")).toThrow();
  });
});

describe("token and digest helpers", () => {
  it("creates parseable device tokens without exposing the secret in IDs", () => {
    const token = createDeviceToken();
    expect(token.value).toMatch(/^wcdt_tk_[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/u);
    expect(parseDeviceToken(token.value)).toEqual({
      tokenId: token.tokenId,
      tokenSecret: token.tokenSecret,
    });
    expect(token.tokenId.includes(token.tokenSecret)).toBe(false);
  });

  it("produces stable SHA-256 and HMAC values", async () => {
    expect(await sha256Hex("abc")).toBe(
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    );
    const first = await hmacSha256Hex("a-secret-at-least-16", "value");
    const second = await hmacSha256Hex("a-secret-at-least-16", "value");
    expect(first).toBe(second);
    expect(first).toHaveLength(64);
    expect(constantTimeEqual(first, second)).toBe(true);
    expect(constantTimeEqual(first, second.replace(/^./u, "0"))).toBe(false);
  });

  it("round-trips base64 and rejects the wrong key length", () => {
    const raw = Uint8Array.from([0, 1, 2, 253, 254, 255]);
    const encoded = bytesToBase64(raw);
    expect(base64ToBytes(encoded)).toEqual(raw);
    expect(() => base64ToBytes(encoded, 32)).toThrow();
  });
});

describe("contact encryption", () => {
  it("uses AES-GCM and separate exact-match lookup digests", async () => {
    const encrypted = await encryptContacts(
      {
        email: " User@Example.com ",
        wechat: " SURTR-WX ",
        other: "support-id",
        notes: "customer requested beta later",
      },
      {
        licenseId: "lic_01",
        keyVersion: 1,
        encryptionKeyBase64: CONTACT_KEY,
        lookupPepper: "lookup-pepper-at-least-16",
      },
    );

    const serialized = bytesToBase64(encrypted.ciphertext);
    expect(serialized.includes("User@Example.com")).toBe(false);
    expect(encrypted.emailLookupDigest).toHaveLength(64);
    expect(encrypted.wechatLookupDigest).toHaveLength(64);
    expect(
      encrypted.emailLookupDigest === encrypted.wechatLookupDigest,
    ).toBe(false);

    await expect(
      decryptContacts(encrypted, {
        licenseId: "lic_01",
        encryptionKeyBase64: CONTACT_KEY,
      }),
    ).resolves.toEqual({
      email: "User@Example.com",
      wechat: "SURTR-WX",
      other: "support-id",
      notes: "customer requested beta later",
    });
  });

  it("binds ciphertext to the license ID and key version", async () => {
    const encrypted = await encryptContacts(
      { email: "user@example.com" },
      {
        licenseId: "lic_01",
        keyVersion: 1,
        encryptionKeyBase64: CONTACT_KEY,
        lookupPepper: "lookup-pepper-at-least-16",
      },
    );

    await expect(
      decryptContacts(encrypted, {
        licenseId: "lic_other",
        encryptionKeyBase64: CONTACT_KEY,
      }),
    ).rejects.toThrow();
  });
});

describe("rollout bucketing", () => {
  it("is stable and bounded", async () => {
    const first = await rolloutBucket("seed", "lic_01", "dev_01");
    const second = await rolloutBucket("seed", "lic_01", "dev_01");
    expect(first).toBe(second);
    expect(first).toBeGreaterThanOrEqual(0);
    expect(first).toBeLessThan(100);
  });
});
