import { afterEach, describe, expect, it, vi } from "vitest";

import { createApp } from "../src/index";
import type { Env } from "../src/types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("staging Access JWKS connectivity probe", () => {
  it("uses manual redirects and returns safe key-count metadata in staging", async () => {
    const fetchStub = vi.fn(async () =>
      new Response(
        JSON.stringify({
          keys: [
            {
              kid: "kid-test-1",
              kty: "RSA",
              alg: "RS256",
              use: "sig",
              n: "secret-public-modulus-shape",
              e: "AQAB",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchStub);
    const env = {
      ENVIRONMENT: "staging",
      ACCESS_JWKS_URL: "https://team.example.cloudflareaccess.com/cdn-cgi/access/certs",
    } as unknown as Env;

    const response = await createApp().request(
      "https://worker.example/v1/health/access-jwks",
      {},
      env,
    );

    expect(response.status).toBe(200);
    expect(fetchStub).toHaveBeenCalledWith(
      "https://team.example.cloudflareaccess.com/cdn-cgi/access/certs",
      expect.objectContaining({ redirect: "manual" }),
    );
    const body = await response.json<Record<string, unknown>>();
    expect(body).toEqual({
      ok: true,
      reachable: true,
      http_status: 200,
      keys_count: 1,
    });
    const serialized = JSON.stringify(body);
    expect(serialized).not.toContain("kid-test-1");
    expect(serialized).not.toContain("secret-public-modulus-shape");
    expect(serialized).not.toContain("cloudflareaccess.com");
  });

  it("returns only a safe error class when the Worker subrequest fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Network connection lost to private target details");
      }),
    );
    const env = {
      ENVIRONMENT: "staging",
      ACCESS_JWKS_URL: "https://team.example.cloudflareaccess.com/cdn-cgi/access/certs",
    } as unknown as Env;

    const response = await createApp().request(
      "https://worker.example/v1/health/access-jwks",
      {},
      env,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      reachable: false,
      error_name: "TypeError",
    });
  });

  it("does not expose the probe outside staging", async () => {
    const response = await createApp().request(
      "https://worker.example/v1/health/access-jwks",
      {},
      {
        ENVIRONMENT: "production",
        ACCESS_JWKS_URL: "https://team.example.cloudflareaccess.com/cdn-cgi/access/certs",
      } as unknown as Env,
    );

    expect(response.status).toBe(404);
  });
});
