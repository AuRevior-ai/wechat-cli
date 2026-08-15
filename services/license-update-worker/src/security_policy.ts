import type { Context } from "hono";

import { authenticateAdmin } from "./auth";
import { ApiError } from "./http";
import { enforceRateLimit } from "./service";
import type { AuthenticatedAdmin, Env, WorkerVariables } from "./types";

type WorkerContext = Context<
  { Bindings: Env; Variables: WorkerVariables },
  any,
  any
>;

export type AdminRateClass = "read" | "write" | "high-risk";

function configuredAdminOrigin(env: Env): string | null {
  const raw = env.ACCESS_ADMIN_ORIGIN;
  if (typeof raw !== "string" || raw.length === 0) return null;
  try {
    const parsed = new URL(raw);
    if (
      parsed.protocol !== "https:" ||
      parsed.username ||
      parsed.password ||
      parsed.pathname !== "/" ||
      parsed.search ||
      parsed.hash
    ) {
      return null;
    }
    return parsed.origin;
  } catch {
    return null;
  }
}

export function assertWorkerOriginAllowed(request: Request, env: Env): void {
  const origin = request.headers.get("Origin");
  if (origin === null) return;

  const path = new URL(request.url).pathname;
  if (path === "/v1/health") return;
  if (path.startsWith("/v1/admin/login/")) {
    const allowed = configuredAdminOrigin(env);
    if (allowed !== null && origin === allowed) return;
  }
  throw new ApiError("ORIGIN_NOT_ALLOWED", "浏览器来源不允许访问该接口。", {
    status: 403,
    retryable: false,
  });
}

export async function enforceAdminLoginRateLimit(
  c: WorkerContext,
): Promise<void> {
  await enforceRateLimit(c, {
    name: "admin-login-ip",
    maximum: 5,
    windowSeconds: 300,
  });
}

const RATE_CLASSES: Record<
  AdminRateClass,
  {
    principalName: string;
    principalMaximum: number;
    ipName: string;
    ipMaximum: number;
  }
> = {
  read: {
    principalName: "admin-read-principal",
    principalMaximum: 120,
    ipName: "admin-read-ip",
    ipMaximum: 240,
  },
  write: {
    principalName: "admin-write-principal",
    principalMaximum: 30,
    ipName: "admin-write-ip",
    ipMaximum: 60,
  },
  "high-risk": {
    principalName: "admin-high-risk-principal",
    principalMaximum: 10,
    ipName: "admin-high-risk-ip",
    ipMaximum: 20,
  },
};

export async function enforceAdminRateLimit(
  c: WorkerContext,
  admin: AuthenticatedAdmin,
  rateClass: AdminRateClass,
): Promise<void> {
  const policy = RATE_CLASSES[rateClass];
  await enforceRateLimit(c, {
    name: policy.principalName,
    maximum: policy.principalMaximum,
    windowSeconds: 60,
    identity: admin.id,
  });
  await enforceRateLimit(c, {
    name: policy.ipName,
    maximum: policy.ipMaximum,
    windowSeconds: 60,
  });
}

export async function authenticateAdminForRoute(
  c: WorkerContext,
  requiredScope: string,
  rateClass: AdminRateClass,
): Promise<AuthenticatedAdmin> {
  const admin = await authenticateAdmin(c, requiredScope, {
    requireRecentAuthentication: rateClass === "high-risk",
  });
  await enforceAdminRateLimit(c, admin, rateClass);
  return admin;
}
