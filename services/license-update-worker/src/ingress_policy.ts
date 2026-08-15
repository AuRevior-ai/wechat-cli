import { ApiError } from "./http";
import type { Env } from "./types";

export type IngressClass = "api" | "admin";

function configuredOriginHost(raw: string | undefined): string | null {
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
    return parsed.hostname.toLowerCase();
  } catch {
    return null;
  }
}

function routeClass(pathname: string): IngressClass | null {
  if (pathname.startsWith("/v1/admin/") || pathname.startsWith("/v1/automation/")) {
    return "admin";
  }
  if (
    pathname === "/v1/health" ||
    pathname.startsWith("/v1/licenses/") ||
    pathname.startsWith("/v1/devices/") ||
    pathname.startsWith("/v1/updates/") ||
    pathname.startsWith("/v1/diagnostics/")
  ) {
    return "api";
  }
  return null;
}

function deny(): never {
  throw new ApiError("INGRESS_NOT_ALLOWED", "请求入口不允许访问该接口。", {
    status: 403,
    retryable: false,
  });
}

export function assertWorkerHostPathAllowed(request: Request, env: Env): IngressClass {
  const url = new URL(request.url);
  const expectedClass = routeClass(url.pathname);

  if (env.ENVIRONMENT !== "production" && env.ENVIRONMENT !== "staging") {
    if (expectedClass !== null) return expectedClass;
    return "api";
  }

  if (expectedClass === null) return deny();

  const apiHost = configuredOriginHost(env.PUBLIC_API_ORIGIN);
  const adminHost = configuredOriginHost(env.ACCESS_ADMIN_ORIGIN);
  if (apiHost === null || adminHost === null || apiHost === adminHost) return deny();

  const requestHost = url.hostname.toLowerCase();
  if (expectedClass === "api" && requestHost === apiHost) return "api";
  if (expectedClass === "admin" && requestHost === adminHost) return "admin";
  return deny();
}
