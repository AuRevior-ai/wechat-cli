import type { Context, Hono } from "hono";

import { authenticateAutomationAssertion } from "./automation_auth";
import { ApiError } from "./http";
import {
  listReleaseMetadataOperation,
  prepareReleasePackageOperation,
  registerDisabledReleaseOperation,
} from "./release_operations";
import type {
  AuthenticatedAutomation,
  Env,
  WorkerVariables,
} from "./types";

type WorkerApp = Hono<{ Bindings: Env; Variables: WorkerVariables }>;
type WorkerContext = Context<
  { Bindings: Env; Variables: WorkerVariables },
  any,
  any
>;

export interface AutomationRouteOptions {
  authenticateAutomation?: (
    env: Env,
    assertion: string,
    requiredScope: string,
  ) => Promise<AuthenticatedAutomation>;
}

async function authenticateAutomationForRoute(
  c: WorkerContext,
  requiredScope: string,
  options: AutomationRouteOptions,
): Promise<AuthenticatedAutomation> {
  const assertion = c.req.header("Cf-Access-Jwt-Assertion");
  if (typeof assertion !== "string" || assertion.length === 0) {
    throw new ApiError("AUTOMATION_IDENTITY_INVALID", "自动化身份断言无效。", {
      status: 401,
      retryable: false,
    });
  }
  const authenticate =
    options.authenticateAutomation ??
    ((env: Env, value: string, scope: string) =>
      authenticateAutomationAssertion(env, value, scope));
  return authenticate(c.env, assertion, requiredScope);
}

export function registerAutomationRoutes(
  app: WorkerApp,
  options: AutomationRouteOptions = {},
): void {
  app.put("/v1/automation/releases/:releaseId/package", async (c) => {
    const automation = await authenticateAutomationForRoute(
      c,
      "releases:upload",
      options,
    );
    const result = await prepareReleasePackageOperation(
      c.env,
      c.req.raw,
      c.req.param("releaseId"),
      {
        actorType: "automation",
        actorId: automation.id,
        requestId: c.get("requestId"),
      },
    );
    return c.json(result.body, result.status as 200);
  });

  app.post("/v1/automation/releases", async (c) => {
    const automation = await authenticateAutomationForRoute(
      c,
      "releases:register",
      options,
    );
    const result = await registerDisabledReleaseOperation(c.env, c.req.raw, {
      actorType: "automation",
      actorId: automation.id,
      requestId: c.get("requestId"),
    });
    return c.json(result.body, result.status as 201);
  });

  app.get("/v1/automation/releases", async (c) => {
    await authenticateAutomationForRoute(c, "releases:read", options);
    return c.json({ releases: await listReleaseMetadataOperation(c.env) });
  });
}
