import { describe, expect, it } from "vitest";

import { createApp } from "../src/index";
import type { Env } from "../src/types";

describe("staging Access JWKS diagnostic cleanup", () => {
  it("does not leave the temporary JWKS connectivity probe exposed", async () => {
    for (const environment of ["staging", "production"]) {
      const response = await createApp().request(
        "https://worker.example/v1/health/access-jwks",
        {},
        { ENVIRONMENT: environment } as unknown as Env,
      );
      expect(response.status, environment).toBe(404);
      await expect(response.json()).resolves.toMatchObject({
        error: { code: "NOT_FOUND" },
      });
    }
  });
});
