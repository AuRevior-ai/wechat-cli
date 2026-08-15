import { Hono } from "hono";

import { registerAdminRoutes } from "./admin";
import {
  registerAdminLoginRoutes,
  type AdminLoginRouteOptions,
} from "./admin_login";
import {
  registerAutomationRoutes,
  type AutomationRouteOptions,
} from "./automation";
import {
  cleanupExpiredDiagnostics,
  registerDiagnosticRoutes,
} from "./diagnostics";
import { ApiError, apiErrorResponse, requestId } from "./http";
import { assertWorkerHostPathAllowed } from "./ingress_policy";
import { registerLicenseRoutes } from "./licenses";
import { assertWorkerOriginAllowed } from "./security_policy";
import { isoNow } from "./service";
import type { Env } from "./types";
import { registerUpdateRoutes } from "./updates";

interface WorkerVariables {
  requestId: string;
}

export function createApp(
  options: AdminLoginRouteOptions & AutomationRouteOptions = {},
): Hono<{
  Bindings: Env;
  Variables: WorkerVariables;
}> {
  const app = new Hono<{ Bindings: Env; Variables: WorkerVariables }>();

  app.use("*", async (c, next) => {
    const id = requestId(c.req.raw);
    c.set("requestId", id);
    await next();
    c.header("X-Request-Id", id);
    c.header("X-Content-Type-Options", "nosniff");
    c.header("Referrer-Policy", "no-referrer");
    c.header("Cache-Control", "no-store");
  });

  app.use("/v1/*", async (c, next) => {
    assertWorkerHostPathAllowed(c.req.raw, c.env);
    assertWorkerOriginAllowed(c.req.raw, c.env);
    await next();
  });

  app.get("/v1/health", (c) =>
    c.json({
      ok: true,
      service: "wechat-cli-license-update",
      environment: c.env.ENVIRONMENT,
      time: isoNow(),
    }),
  );

  registerLicenseRoutes(app);
  registerUpdateRoutes(app);
  registerDiagnosticRoutes(app);
  registerAdminLoginRoutes(app, options);
  registerAutomationRoutes(app, options);
  registerAdminRoutes(app);

  app.notFound((c) => {
    const id = c.get("requestId") || requestId(c.req.raw);
    return apiErrorResponse(
      c,
      new ApiError("NOT_FOUND", "接口不存在。", { status: 404 }),
      id,
    );
  });

  app.onError((error, c) => {
    const id = c.get("requestId") || requestId(c.req.raw);
    if (error instanceof ApiError) {
      return apiErrorResponse(c, error, id);
    }
    const localDetails =
      c.env.ENVIRONMENT === "local" && error instanceof Error
        ? {
            error_name: error.name,
            error_message: error.message,
          }
        : undefined;
    console.error(
      JSON.stringify({
        level: "error",
        event: "unhandled_exception",
        request_id: id,
        error_name: error instanceof Error ? error.name : "UnknownError",
        ...(localDetails === undefined ? {} : localDetails),
      }),
    );
    return apiErrorResponse(
      c,
      new ApiError("INTERNAL_ERROR", "服务暂时无法完成请求。", {
        status: 500,
        retryable: true,
        ...(localDetails === undefined ? {} : { details: localDetails }),
      }),
      id,
    );
  });

  return app;
}

const app = createApp();

async function cleanupExpired(env: Env): Promise<void> {
  const now = isoNow();
  await cleanupExpiredDiagnostics(env, new Date(now));
  await env.DB.batch([
    env.DB.prepare("DELETE FROM rate_limit_windows WHERE expires_at <= ?").bind(now),
    env.DB.prepare("DELETE FROM idempotency_records WHERE expires_at <= ?").bind(now),
    env.DB.prepare("DELETE FROM download_tickets WHERE expires_at <= ?").bind(now),
  ]);
}

export default {
  fetch: app.fetch,
  async scheduled(
    _controller: ScheduledController,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<void> {
    ctx.waitUntil(cleanupExpired(env));
  },
};
