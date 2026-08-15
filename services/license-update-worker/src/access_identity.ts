import { ApiError } from "./http";

export interface VerifiedAccessIdentity {
  subject: string;
  identity: string;
}

export interface AccessJwtVerifierOptions {
  issuer: string;
  jwksUrl: string;
  audiences: string[];
  identityClaim: string;
  fetchJwks: (url: string) => Promise<{ keys: JsonWebKey[] }>;
  cacheTtlSeconds?: number;
  clockSkewSeconds?: number;
  now?: () => Date;
}

interface JwtHeader {
  alg: string;
  kid: string;
  jku?: unknown;
  x5u?: unknown;
}

type AccessJwk = JsonWebKey & {
  kid?: string;
  alg?: string;
  use?: string;
};

interface CachedJwks {
  fetchedAtMs: number;
  keys: Map<string, AccessJwk>;
}

function invalidIdentity(message = "管理员身份断言无效。", cause?: unknown): ApiError {
  return new ApiError("ADMIN_IDENTITY_INVALID", message, {
    status: 401,
    retryable: false,
    ...(cause === undefined ? {} : { cause }),
  });
}

function decodeBase64UrlJson(value: string): Record<string, unknown> {
  if (!/^[A-Za-z0-9_-]+$/u.test(value)) {
    throw invalidIdentity();
  }
  try {
    const padded = value.replaceAll("-", "+").replaceAll("_", "/").padEnd(
      Math.ceil(value.length / 4) * 4,
      "=",
    );
    const binary = atob(padded);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    const parsed = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      throw new TypeError("JWT object expected");
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw invalidIdentity("管理员身份断言格式无效。", error);
  }
}

function decodeBase64UrlBytes(value: string): Uint8Array<ArrayBuffer> {
  if (!/^[A-Za-z0-9_-]+$/u.test(value)) {
    throw invalidIdentity();
  }
  try {
    const padded = value.replaceAll("-", "+").replaceAll("_", "/").padEnd(
      Math.ceil(value.length / 4) * 4,
      "=",
    );
    const binary = atob(padded);
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  } catch (error) {
    throw invalidIdentity("管理员身份断言签名格式无效。", error);
  }
}

function numericClaim(payload: Record<string, unknown>, name: string): number {
  const value = payload[name];
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value <= 0) {
    throw invalidIdentity();
  }
  return value;
}

function audienceValues(value: unknown): string[] {
  if (typeof value === "string" && value.length > 0) return [value];
  if (
    Array.isArray(value) &&
    value.length > 0 &&
    value.length <= 16 &&
    value.every((item) => typeof item === "string" && item.length > 0)
  ) {
    return value as string[];
  }
  throw invalidIdentity();
}

export async function fetchAccessJwks(url: string): Promise<{ keys: JsonWebKey[] }> {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    redirect: "manual",
  });
  if (response.status !== 200) {
    throw new Error(`Access JWKS returned HTTP ${response.status}`);
  }
  const value = await response.json<unknown>();
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Access JWKS response is invalid");
  }
  const keys = (value as { keys?: unknown }).keys;
  if (!Array.isArray(keys)) {
    throw new Error("Access JWKS keys are invalid");
  }
  return { keys: keys as JsonWebKey[] };
}

export class AccessJwtVerifier {
  private readonly issuer: string;
  private readonly jwksUrl: string;
  private readonly audiences: Set<string>;
  private readonly identityClaim: string;
  private readonly fetchJwks: AccessJwtVerifierOptions["fetchJwks"];
  private readonly cacheTtlMs: number;
  private readonly clockSkewSeconds: number;
  private readonly now: () => Date;
  private cache: CachedJwks | null = null;

  constructor(options: AccessJwtVerifierOptions) {
    const issuerUrl = new URL(options.issuer);
    const jwksUrl = new URL(options.jwksUrl);
    if (
      issuerUrl.protocol !== "https:" ||
      jwksUrl.protocol !== "https:" ||
      issuerUrl.username ||
      issuerUrl.password ||
      jwksUrl.username ||
      jwksUrl.password ||
      issuerUrl.origin !== jwksUrl.origin
    ) {
      throw new TypeError("Access issuer/JWKS configuration must use one HTTPS origin");
    }
    if (!options.audiences.length || options.audiences.length > 8) {
      throw new TypeError("Access audience allowlist is invalid");
    }
    if (!/^[A-Za-z0-9_.-]{1,64}$/u.test(options.identityClaim)) {
      throw new TypeError("Access identity claim is invalid");
    }

    this.issuer = options.issuer.replace(/\/$/u, "");
    this.jwksUrl = options.jwksUrl;
    this.audiences = new Set(options.audiences);
    this.identityClaim = options.identityClaim;
    this.fetchJwks = options.fetchJwks;
    this.cacheTtlMs = Math.max(1, Math.min(options.cacheTtlSeconds ?? 300, 3600)) * 1000;
    this.clockSkewSeconds = Math.max(0, Math.min(options.clockSkewSeconds ?? 30, 120));
    this.now = options.now ?? (() => new Date());
  }

  private cacheFresh(nowMs: number): boolean {
    return this.cache !== null && nowMs - this.cache.fetchedAtMs <= this.cacheTtlMs;
  }

  private async refreshJwks(nowMs: number): Promise<void> {
    let response: { keys: JsonWebKey[] };
    try {
      response = await this.fetchJwks(this.jwksUrl);
    } catch (error) {
      throw invalidIdentity("管理员身份密钥当前不可用。", error);
    }
    if (!Array.isArray(response.keys) || response.keys.length === 0 || response.keys.length > 64) {
      throw invalidIdentity("管理员身份密钥集合无效。");
    }
    const keys = new Map<string, AccessJwk>();
    for (const rawKey of response.keys) {
      const key = rawKey as AccessJwk;
      const kid = key.kid;
      if (
        typeof kid !== "string" ||
        !kid ||
        key.kty !== "RSA" ||
        (key.use !== undefined && key.use !== "sig") ||
        (key.alg !== undefined && key.alg !== "RS256")
      ) {
        continue;
      }
      keys.set(kid, key);
    }
    if (keys.size === 0) {
      throw invalidIdentity("管理员身份密钥集合无可用签名密钥。");
    }
    this.cache = { fetchedAtMs: nowMs, keys };
  }

  private async keyFor(kid: string, nowMs: number): Promise<AccessJwk> {
    if (this.cacheFresh(nowMs)) {
      const cached = this.cache?.keys.get(kid);
      if (cached !== undefined) return cached;
      await this.refreshJwks(nowMs);
      const refreshed = this.cache?.keys.get(kid);
      if (refreshed !== undefined) return refreshed;
      throw invalidIdentity("管理员身份签名密钥未知。");
    }

    await this.refreshJwks(nowMs);
    const first = this.cache?.keys.get(kid);
    if (first !== undefined) return first;
    await this.refreshJwks(nowMs);
    const second = this.cache?.keys.get(kid);
    if (second !== undefined) return second;
    throw invalidIdentity("管理员身份签名密钥未知。");
  }

  async verify(assertion: string): Promise<VerifiedAccessIdentity> {
    if (typeof assertion !== "string" || assertion.length < 32 || assertion.length > 16_384) {
      throw invalidIdentity();
    }
    const parts = assertion.split(".");
    if (parts.length !== 3 || parts.some((part) => part.length === 0)) {
      throw invalidIdentity();
    }
    const [encodedHeader, encodedPayload, encodedSignature] = parts as [string, string, string];
    const rawHeader = decodeBase64UrlJson(encodedHeader);
    const rawPayload = decodeBase64UrlJson(encodedPayload);
    if (
      rawHeader.alg !== "RS256" ||
      typeof rawHeader.kid !== "string" ||
      !rawHeader.kid ||
      rawHeader.jku !== undefined ||
      rawHeader.x5u !== undefined
    ) {
      throw invalidIdentity();
    }
    const header = rawHeader as unknown as JwtHeader;

    const nowSeconds = Math.floor(this.now().getTime() / 1000);
    if (!Number.isSafeInteger(nowSeconds) || nowSeconds <= 0) {
      throw invalidIdentity("管理员身份验证时钟无效。");
    }
    const exp = numericClaim(rawPayload, "exp");
    const nbf = numericClaim(rawPayload, "nbf");
    const iat = numericClaim(rawPayload, "iat");
    if (
      exp <= nowSeconds - this.clockSkewSeconds ||
      nbf > nowSeconds + this.clockSkewSeconds ||
      iat > nowSeconds + this.clockSkewSeconds ||
      iat > exp ||
      nbf > exp
    ) {
      throw invalidIdentity();
    }
    const issuer = rawPayload.iss;
    if (typeof issuer !== "string" || issuer.replace(/\/$/u, "") !== this.issuer) {
      throw invalidIdentity();
    }
    const audiences = audienceValues(rawPayload.aud);
    if (!audiences.some((audience) => this.audiences.has(audience))) {
      throw invalidIdentity();
    }
    const subject = rawPayload.sub;
    const identity = rawPayload[this.identityClaim];
    if (
      typeof subject !== "string" ||
      !subject ||
      subject.length > 512 ||
      typeof identity !== "string" ||
      !identity ||
      identity.length > 512
    ) {
      throw invalidIdentity();
    }

    const jwk = await this.keyFor(header.kid, this.now().getTime());
    let key: CryptoKey;
    try {
      key = await crypto.subtle.importKey(
        "jwk",
        jwk,
        { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
        false,
        ["verify"],
      );
    } catch (error) {
      throw invalidIdentity("管理员身份签名密钥无效。", error);
    }
    const verified = await crypto.subtle.verify(
      "RSASSA-PKCS1-v1_5",
      key,
      decodeBase64UrlBytes(encodedSignature),
      new TextEncoder().encode(`${encodedHeader}.${encodedPayload}`),
    );
    if (!verified) {
      throw invalidIdentity();
    }
    return {
      subject,
      identity: identity.trim().toLowerCase(),
    };
  }
}
