import { describe, expect, it, vi } from "vitest";

type AdminLoginModule = {
  fetchAccessJwks?: (url: string) => Promise<{ keys: JsonWebKey[] }>;
  AccessJwtVerifier?: new (options: {
    issuer: string;
    jwksUrl: string;
    audiences: string[];
    identityClaim: string;
    fetchJwks: (url: string) => Promise<{ keys: JsonWebKey[] }>;
    cacheTtlSeconds?: number;
    clockSkewSeconds?: number;
    now?: () => Date;
  }) => {
    verify(assertion: string): Promise<{ subject: string; identity: string }>;
  };
};

async function loadAdminLoginModule(): Promise<AdminLoginModule> {
  const modulePath = "../src/admin_login";
  try {
    return (await import(modulePath)) as AdminLoginModule;
  } catch {
    return {};
  }
}

function base64Url(value: Uint8Array | string): string {
  const bytes = typeof value === "string" ? new TextEncoder().encode(value) : value;
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/u, "");
}

type TestJwk = JsonWebKey & { kid: string; alg: string; use: string };

async function rsaFixture(): Promise<{ privateKey: CryptoKey; jwk: TestJwk }> {
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
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  return {
    privateKey: pair.privateKey,
    jwk: { ...jwk, kid: "kid-1", alg: "RS256", use: "sig" } as TestJwk,
  };
}

async function signedJwt(options: {
  privateKey: CryptoKey;
  header?: Record<string, unknown>;
  payload?: Record<string, unknown>;
}): Promise<string> {
  const now = 1_786_579_200; // 2026-08-13T00:00:00Z
  const header = {
    alg: "RS256",
    typ: "JWT",
    kid: "kid-1",
    ...(options.header ?? {}),
  };
  const payload = {
    iss: "https://team.example.cloudflareaccess.com",
    aud: ["access-app-aud"],
    sub: "access-subject-1",
    email: "Admin@Example.com",
    iat: now - 30,
    nbf: now - 30,
    exp: now + 300,
    ...(options.payload ?? {}),
  };
  const signingInput = `${base64Url(JSON.stringify(header))}.${base64Url(JSON.stringify(payload))}`;
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    options.privateKey,
    new TextEncoder().encode(signingInput),
  );
  return `${signingInput}.${base64Url(new Uint8Array(signature))}`;
}

async function verifierFixture() {
  const module = await loadAdminLoginModule();
  expect(module.AccessJwtVerifier).toBeTypeOf("function");
  const fixture = await rsaFixture();
  const fetchJwks = vi.fn(async (url: string) => {
    expect(url).toBe("https://team.example.cloudflareaccess.com/cdn-cgi/access/certs");
    return { keys: [fixture.jwk] };
  });
  const verifier = new module.AccessJwtVerifier!({
    issuer: "https://team.example.cloudflareaccess.com",
    jwksUrl: "https://team.example.cloudflareaccess.com/cdn-cgi/access/certs",
    audiences: ["access-app-aud"],
    identityClaim: "email",
    fetchJwks,
    now: () => new Date("2026-08-13T00:00:00Z"),
    clockSkewSeconds: 30,
    cacheTtlSeconds: 300,
  });
  return { verifier, fixture, fetchJwks };
}

describe("Cloudflare Access JWT verification", () => {
  it("fetches the exact Access JWKS endpoint with manual redirect handling", async () => {
    const module = await loadAdminLoginModule();
    expect(module.fetchAccessJwks).toBeTypeOf("function");
    const fetchStub = vi.fn(async () =>
      new Response(JSON.stringify({ keys: [{ kid: "kid-1" }] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchStub);
    try {
      await expect(
        module.fetchAccessJwks!("https://team.example.cloudflareaccess.com/cdn-cgi/access/certs"),
      ).resolves.toEqual({ keys: [{ kid: "kid-1" }] });
      expect(fetchStub).toHaveBeenCalledWith(
        "https://team.example.cloudflareaccess.com/cdn-cgi/access/certs",
        expect.objectContaining({ redirect: "manual" }),
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("cryptographically verifies RS256 and normalizes the verified identity", async () => {
    const { verifier, fixture } = await verifierFixture();
    const assertion = await signedJwt({ privateKey: fixture.privateKey });

    await expect(verifier.verify(assertion)).resolves.toEqual({
      subject: "access-subject-1",
      identity: "admin@example.com",
    });
  });

  it("rejects a wrong signature even when claims look valid", async () => {
    const { verifier } = await verifierFixture();
    const attacker = await rsaFixture();
    const assertion = await signedJwt({ privateKey: attacker.privateKey });

    await expect(verifier.verify(assertion)).rejects.toMatchObject({
      code: "ADMIN_IDENTITY_INVALID",
    });
  });

  it.each([
    ["none algorithm", { header: { alg: "none" } }],
    ["wrong issuer", { payload: { iss: "https://attacker.example" } }],
    ["wrong audience", { payload: { aud: ["other-app"] } }],
    ["expired assertion", { payload: { exp: 1_786_578_000 } }],
    ["future nbf", { payload: { nbf: 1_786_580_000 } }],
    ["missing iat", { payload: { iat: null } }],
    ["missing subject", { payload: { sub: null } }],
    ["missing identity", { payload: { email: null } }],
  ])("rejects %s", async (_name, mutation) => {
    const { verifier, fixture } = await verifierFixture();
    const assertion = await signedJwt({
      privateKey: fixture.privateKey,
      ...("header" in mutation ? { header: mutation.header } : {}),
      ...("payload" in mutation ? { payload: mutation.payload } : {}),
    });

    await expect(verifier.verify(assertion)).rejects.toMatchObject({
      code: "ADMIN_IDENTITY_INVALID",
    });
  });

  it("rejects token-controlled jku and x5u key discovery", async () => {
    const { verifier, fixture } = await verifierFixture();
    for (const header of [
      { jku: "https://attacker.example/jwks.json" },
      { x5u: "https://attacker.example/cert.pem" },
    ]) {
      const assertion = await signedJwt({ privateKey: fixture.privateKey, header });
      await expect(verifier.verify(assertion)).rejects.toMatchObject({
        code: "ADMIN_IDENTITY_INVALID",
      });
    }
  });

  it("refreshes an unknown kid at most once and then fails closed", async () => {
    const module = await loadAdminLoginModule();
    expect(module.AccessJwtVerifier).toBeTypeOf("function");
    const fixture = await rsaFixture();
    const fetchJwks = vi.fn(async () => ({ keys: [fixture.jwk] }));
    const verifier = new module.AccessJwtVerifier!({
      issuer: "https://team.example.cloudflareaccess.com",
      jwksUrl: "https://team.example.cloudflareaccess.com/cdn-cgi/access/certs",
      audiences: ["access-app-aud"],
      identityClaim: "email",
      fetchJwks,
      now: () => new Date("2026-08-13T00:00:00Z"),
    });
    const assertion = await signedJwt({
      privateKey: fixture.privateKey,
      header: { kid: "unknown-kid" },
    });

    await expect(verifier.verify(assertion)).rejects.toMatchObject({
      code: "ADMIN_IDENTITY_INVALID",
    });
    expect(fetchJwks).toHaveBeenCalledTimes(2);
  });

  it("uses a bounded cached key during JWKS outage but fails when cache is stale", async () => {
    const module = await loadAdminLoginModule();
    expect(module.AccessJwtVerifier).toBeTypeOf("function");
    const fixture = await rsaFixture();
    let now = new Date("2026-08-13T00:00:00Z");
    const fetchJwks = vi
      .fn<(url: string) => Promise<{ keys: JsonWebKey[] }>>()
      .mockResolvedValueOnce({ keys: [fixture.jwk] })
      .mockRejectedValue(new Error("jwks unavailable"));
    const verifier = new module.AccessJwtVerifier!({
      issuer: "https://team.example.cloudflareaccess.com",
      jwksUrl: "https://team.example.cloudflareaccess.com/cdn-cgi/access/certs",
      audiences: ["access-app-aud"],
      identityClaim: "email",
      fetchJwks,
      now: () => now,
      cacheTtlSeconds: 60,
    });
    const assertion = await signedJwt({ privateKey: fixture.privateKey });

    await expect(verifier.verify(assertion)).resolves.toMatchObject({
      identity: "admin@example.com",
    });
    now = new Date("2026-08-13T00:00:30Z");
    await expect(verifier.verify(assertion)).resolves.toMatchObject({
      identity: "admin@example.com",
    });
    now = new Date("2026-08-13T00:02:00Z");
    await expect(verifier.verify(assertion)).rejects.toMatchObject({
      code: "ADMIN_IDENTITY_INVALID",
    });
  });
});
