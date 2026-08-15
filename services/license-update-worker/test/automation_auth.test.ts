import { beforeAll, describe, expect, it, vi } from "vitest";

import { authenticateAutomationAssertion } from "../src/automation_auth";
import type { Env } from "../src/types";

function base64Url(value: Uint8Array | string): string {
  const bytes = typeof value === "string" ? new TextEncoder().encode(value) : value;
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/u, "");
}

type TestJwk = JsonWebKey & { kid: string; alg: string; use: string };
let privateKey: CryptoKey;
let publicJwk: TestJwk;

beforeAll(async () => {
  const pair = await crypto.subtle.generateKey(
    {
      name: "RSASSA-PKCS1-v1_5",
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: "SHA-256",
    },
    true,
    ["sign", "verify"],
  );
  privateKey = pair.privateKey;
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  publicJwk = { ...jwk, kid: "automation-kid", alg: "RS256", use: "sig" } as TestJwk;
});

async function signedJwt(payloadMutation: Record<string, unknown> = {}, key = privateKey): Promise<string> {
  const now = 1_786_579_200;
  const header = { alg: "RS256", typ: "JWT", kid: "automation-kid" };
  const payload = {
    iss: "https://team.example.cloudflareaccess.com",
    aud: ["automation-aud"],
    sub: "service-token-subject",
    common_name: "release-automation-client",
    iat: now - 30,
    nbf: now - 30,
    exp: now + 300,
    ...payloadMutation,
  };
  const signingInput = `${base64Url(JSON.stringify(header))}.${base64Url(JSON.stringify(payload))}`;
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    new TextEncoder().encode(signingInput),
  );
  return `${signingInput}.${base64Url(new Uint8Array(signature))}`;
}

function dbForPrincipal(options?: {
  status?: "active" | "revoked";
  identity?: string;
  scopes?: string[];
}) {
  const row = {
    id: "automation_principal_1",
    identity: options?.identity ?? "release-automation-client",
    scopes_json: JSON.stringify(options?.scopes ?? ["releases:upload", "releases:read", "releases:register"]),
    status: options?.status ?? "active",
  };
  return {
    prepare(statement: string) {
      expect(statement).toContain("FROM automation_principals");
      let identity = "";
      return {
        bind(value: unknown) {
          identity = String(value);
          return this;
        },
        async first<T>() {
          return (identity === row.identity ? row : null) as T;
        },
      };
    },
  } as unknown as D1Database;
}

function env(options?: Parameters<typeof dbForPrincipal>[0]): Env {
  return {
    ENVIRONMENT: "production",
    DB: dbForPrincipal(options),
    ACCESS_JWT_ISSUER: "https://team.example.cloudflareaccess.com",
    ACCESS_JWKS_URL: "https://team.example.cloudflareaccess.com/cdn-cgi/access/certs",
    ACCESS_AUTOMATION_AUDIENCES: "automation-aud",
    ACCESS_AUTOMATION_IDENTITY_CLAIM: "common_name",
    ACCESS_AUTOMATION_IDENTITIES: "release-automation-client",
  } as unknown as Env;
}

function verifierOptions() {
  return {
    fetchJwks: vi.fn(async () => ({ keys: [publicJwk] })),
    now: () => new Date("2026-08-13T00:00:00Z"),
  };
}

describe("production automation identity", () => {
  it("accepts an exact automation audience, allowlisted identity, active principal, and exact scope", async () => {
    const assertion = await signedJwt();
    await expect(
      authenticateAutomationAssertion(env(), assertion, "releases:register", verifierOptions()),
    ).resolves.toMatchObject({
      id: "automation_principal_1",
      identity: "release-automation-client",
      authMode: "access_service",
    });
  });

  it.each([
    ["human audience", { aud: ["human-aud"] }],
    ["wrong issuer", { iss: "https://attacker.example" }],
    ["expired assertion", { exp: 1_786_578_000 }],
    ["future nbf", { nbf: 1_786_580_000 }],
  ])("rejects %s", async (_name, mutation) => {
    const assertion = await signedJwt(mutation);
    await expect(
      authenticateAutomationAssertion(env(), assertion, "releases:read", verifierOptions()),
    ).rejects.toMatchObject({ code: "AUTOMATION_IDENTITY_INVALID" });
  });

  it("rejects a wrong signature", async () => {
    const attacker = await crypto.subtle.generateKey(
      {
        name: "RSASSA-PKCS1-v1_5",
        modulusLength: 2048,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: "SHA-256",
      },
      true,
      ["sign", "verify"],
    );
    const assertion = await signedJwt({}, attacker.privateKey);
    await expect(
      authenticateAutomationAssertion(env(), assertion, "releases:read", verifierOptions()),
    ).rejects.toMatchObject({ code: "AUTOMATION_IDENTITY_INVALID" });
  });

  it("rejects a verified identity outside the configured service-token allowlist", async () => {
    const assertion = await signedJwt({ common_name: "other-service-client" });
    await expect(
      authenticateAutomationAssertion(env(), assertion, "releases:read", verifierOptions()),
    ).rejects.toMatchObject({ code: "AUTOMATION_PRINCIPAL_DENIED" });
  });

  it("rejects revoked automation principals", async () => {
    const assertion = await signedJwt();
    await expect(
      authenticateAutomationAssertion(
        env({ status: "revoked" }),
        assertion,
        "releases:read",
        verifierOptions(),
      ),
    ).rejects.toMatchObject({ code: "AUTOMATION_PRINCIPAL_DENIED" });
  });

  it("rejects wildcard machine scopes", async () => {
    const assertion = await signedJwt();
    await expect(
      authenticateAutomationAssertion(
        env({ scopes: ["*"] }),
        assertion,
        "releases:read",
        verifierOptions(),
      ),
    ).rejects.toMatchObject({ code: "AUTOMATION_PRINCIPAL_INVALID" });
  });

  it("fails closed when production has only the legacy human audience configuration", async () => {
    const assertion = await signedJwt();
    const legacy = {
      ...env(),
      ACCESS_AUTOMATION_AUDIENCES: undefined,
      ACCESS_AUDIENCES: "automation-aud",
    } as unknown as Env;
    await expect(
      authenticateAutomationAssertion(legacy, assertion, "releases:read", verifierOptions()),
    ).rejects.toMatchObject({ code: "AUTOMATION_CONFIG_INVALID" });
  });
});
