import { describe, expect, it } from "vitest";

import { createApp } from "../src/index";
import { assertWorkerHostPathAllowed } from "../src/ingress_policy";
import type { Env } from "../src/types";

function productionEnv(): Env {
  return {
    ENVIRONMENT: "production",
    PUBLIC_API_ORIGIN: "https://api.prod.example.test",
    ACCESS_ADMIN_ORIGIN: "https://admin.prod.example.test",
  } as unknown as Env;
}

describe("production Worker Host + Path authority", () => {
  it.each([
    ["https://api.prod.example.test/v1/health", "api"],
    ["https://api.prod.example.test/v1/licenses/activate", "api"],
    ["https://api.prod.example.test/v1/devices/validate", "api"],
    ["https://api.prod.example.test/v1/updates/check", "api"],
    ["https://api.prod.example.test/v1/updates/download", "api"],
    ["https://api.prod.example.test/v1/diagnostics/sessions", "api"],
    ["https://admin.prod.example.test/v1/admin/releases", "admin"],
    ["https://admin.prod.example.test/v1/automation/releases", "admin"],
  ])("allows the exact host/path class for %s", (url, expected) => {
    expect(assertWorkerHostPathAllowed(new Request(url), productionEnv())).toBe(expected);
  });

  it.each([
    "https://api.prod.example.test/v1/admin/releases",
    "https://api.prod.example.test/v1/automation/releases",
    "https://admin.prod.example.test/v1/licenses/activate",
    "https://wechat-cli-license-update.workers.dev/v1/admin/releases",
    "https://wechat-cli-license-update-staging.aurevior-ai.workers.dev/v1/admin/releases",
    "https://unknown.prod.example.test/v1/updates/check",
    "https://api.prod.example.test/v1/unclassified",
  ])("rejects unauthorized production ingress %s", (url) => {
    expect(() => assertWorkerHostPathAllowed(new Request(url), productionEnv())).toThrowError(
      expect.objectContaining({ code: "INGRESS_NOT_ALLOWED", status: 403 }),
    );
  });

  it("runs before admin authentication in the application middleware chain", async () => {
    const response = await createApp().request(
      "https://api.prod.example.test/v1/admin/releases",
      {},
      productionEnv(),
    );
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error: { code: "INGRESS_NOT_ALLOWED" },
    });
  });

  it("keeps local test compatibility without trusting forwarded host headers", () => {
    const request = new Request("https://local.example.test/v1/admin/releases", {
      headers: { "X-Forwarded-Host": "api.prod.example.test" },
    });
    expect(
      assertWorkerHostPathAllowed(request, { ENVIRONMENT: "local" } as Env),
    ).toBe("admin");
  });
});
