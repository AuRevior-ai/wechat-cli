import { AccessJwtVerifier, fetchAccessJwks } from "./access_identity";
import { ApiError } from "./http";
import type { AuthenticatedAutomation, Env } from "./types";

export interface AutomationAuthOptions {
  fetchJwks?: (url: string) => Promise<{ keys: JsonWebKey[] }>;
  now?: () => Date;
}

function automationError(
  code: "AUTOMATION_CONFIG_INVALID" | "AUTOMATION_IDENTITY_INVALID" | "AUTOMATION_PRINCIPAL_DENIED" | "AUTOMATION_PRINCIPAL_INVALID" | "AUTOMATION_SCOPE_DENIED",
  message: string,
  status: number,
  cause?: unknown,
): ApiError {
  return new ApiError(code, message, {
    status,
    retryable: false,
    ...(cause === undefined ? {} : { cause }),
  });
}

function splitConfiguredValues(raw: string | undefined, maximum: number): string[] {
  if (typeof raw !== "string") return [];
  const values = raw
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (values.length === 0 || values.length > maximum || new Set(values).size !== values.length) {
    return [];
  }
  return values;
}

function machineScopes(value: unknown): Set<string> {
  let parsed = value;
  if (typeof parsed === "string") {
    try {
      parsed = JSON.parse(parsed);
    } catch {
      parsed = [];
    }
  }
  if (
    !Array.isArray(parsed) ||
    parsed.length === 0 ||
    parsed.length > 16 ||
    !parsed.every(
      (scope) =>
        typeof scope === "string" &&
        /^[A-Za-z0-9:._-]{1,128}$/u.test(scope) &&
        !scope.includes("*"),
    )
  ) {
    throw automationError(
      "AUTOMATION_PRINCIPAL_INVALID",
      "自动化主体权限数据无效。",
      401,
    );
  }
  return new Set(parsed as string[]);
}

export async function authenticateAutomationAssertion(
  env: Env,
  assertion: string,
  requiredScope: string,
  options: AutomationAuthOptions = {},
): Promise<AuthenticatedAutomation> {
  const issuer = env.ACCESS_JWT_ISSUER;
  const jwksUrl = env.ACCESS_JWKS_URL;
  const audiences = splitConfiguredValues(env.ACCESS_AUTOMATION_AUDIENCES, 8);
  const identityClaim = env.ACCESS_AUTOMATION_IDENTITY_CLAIM;
  const identities = splitConfiguredValues(env.ACCESS_AUTOMATION_IDENTITIES, 32).map((value) =>
    value.toLowerCase(),
  );
  if (
    typeof issuer !== "string" ||
    typeof jwksUrl !== "string" ||
    audiences.length === 0 ||
    typeof identityClaim !== "string" ||
    identityClaim.length === 0 ||
    identities.length === 0
  ) {
    throw automationError(
      "AUTOMATION_CONFIG_INVALID",
      "自动化 Access 身份配置未完成。",
      503,
    );
  }

  let verifier: AccessJwtVerifier;
  try {
    verifier = new AccessJwtVerifier({
      issuer,
      jwksUrl,
      audiences,
      identityClaim,
      fetchJwks: options.fetchJwks ?? fetchAccessJwks,
      ...(options.now === undefined ? {} : { now: options.now }),
    });
  } catch (error) {
    throw automationError(
      "AUTOMATION_CONFIG_INVALID",
      "自动化 Access 身份配置无效。",
      503,
      error,
    );
  }

  let verified: { subject: string; identity: string };
  try {
    verified = await verifier.verify(assertion);
  } catch (error) {
    throw automationError(
      "AUTOMATION_IDENTITY_INVALID",
      "自动化身份断言无效。",
      401,
      error,
    );
  }
  const identity = verified.identity.trim().toLowerCase();
  if (!identities.includes(identity)) {
    throw automationError(
      "AUTOMATION_PRINCIPAL_DENIED",
      "自动化身份未获授权。",
      403,
    );
  }

  const principal = await env.DB.prepare(
    `SELECT id, identity, scopes_json, status
       FROM automation_principals
      WHERE identity = ?
      LIMIT 1`,
  )
    .bind(identity)
    .first<Record<string, unknown>>();
  if (principal === null || principal.status !== "active") {
    throw automationError(
      "AUTOMATION_PRINCIPAL_DENIED",
      "自动化主体未获授权。",
      403,
    );
  }
  if (String(principal.identity ?? "").trim().toLowerCase() !== identity) {
    throw automationError(
      "AUTOMATION_PRINCIPAL_INVALID",
      "自动化主体身份数据无效。",
      401,
    );
  }
  const scopes = machineScopes(principal.scopes_json);
  if (!scopes.has(requiredScope)) {
    throw automationError(
      "AUTOMATION_SCOPE_DENIED",
      "自动化主体缺少所需权限。",
      403,
    );
  }
  const now = options.now?.() ?? new Date();
  return {
    id: String(principal.id),
    identity,
    scopes,
    authMode: "access_service",
    authenticatedAt: now.toISOString(),
  };
}
