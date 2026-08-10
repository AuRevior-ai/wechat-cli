import { describe, expect, it } from "vitest";

import { ApiError } from "../src/http";
import { d1BlobBytes, fetchGithubReleaseAsset } from "../src/updates";

describe("D1 BLOB decoding", () => {
  it("accepts ArrayBuffer and typed-array values", () => {
    const buffer = Uint8Array.from([1, 2, 3]).buffer;
    expect([...d1BlobBytes(buffer, "manifest")]).toEqual([1, 2, 3]);
    expect([...d1BlobBytes(Uint8Array.from([4, 5]), "signature")]).toEqual([
      4,
      5,
    ]);
  });

  it("accepts the plain byte arrays returned by local D1", () => {
    expect([...d1BlobBytes([0, 127, 255], "manifest")]).toEqual([
      0,
      127,
      255,
    ]);
  });

  it("rejects strings and out-of-range array values", () => {
    for (const value of ["AQID", [0, 256], [1, -1], [1, 1.5]]) {
      try {
        d1BlobBytes(value, "manifest");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).code).toBe("RELEASE_STATE_INVALID");
        continue;
      }
      throw new Error("invalid D1 BLOB value was accepted");
    }
  });
});

describe("GitHub release asset fetch", () => {
  it("follows HTTPS redirects manually without forwarding authorization", async () => {
    const calls: Array<{
      url: string;
      headers: Headers;
      redirect: RequestRedirect | undefined;
    }> = [];
    const fakeFetch = async (
      input: RequestInfo | URL,
      init?: RequestInit,
    ): Promise<Response> => {
      const url = String(input);
      calls.push({
        url,
        headers: new Headers(init?.headers),
        redirect: init?.redirect,
      });
      if (calls.length === 1) {
        return new Response(null, {
          status: 302,
          headers: {
            Location: "https://objects.githubusercontent.com/private-asset",
          },
        });
      }
      return new Response(new Uint8Array([1]), {
        status: 206,
        headers: { "Content-Range": "bytes 0-0/1" },
      });
    };
    const headers = new Headers({
      Accept: "application/octet-stream",
      Authorization: "Bearer github-secret",
      Range: "bytes=0-0",
      "User-Agent": "wechat-cli-license-update-worker",
    });

    const response = await fetchGithubReleaseAsset(
      "https://api.github.com/repos/org/repo/releases/assets/123",
      headers,
      fakeFetch as typeof fetch,
    );

    expect(response.status).toBe(206);
    expect(calls).toHaveLength(2);
    expect(calls[0]?.redirect).toBe("manual");
    expect(calls[0]?.headers.get("Authorization")).toBe("Bearer github-secret");
    expect(calls[1]?.url).toBe(
      "https://objects.githubusercontent.com/private-asset",
    );
    expect(calls[1]?.headers.get("Authorization")).toBeNull();
    expect(calls[1]?.headers.get("Range")).toBe("bytes=0-0");
  });

  it("rejects non-HTTPS GitHub asset redirects", async () => {
    const fakeFetch = async (): Promise<Response> =>
      new Response(null, {
        status: 302,
        headers: { Location: "http://example.invalid/private-asset" },
      });

    await expect(
      fetchGithubReleaseAsset(
        "https://api.github.com/repos/org/repo/releases/assets/123",
        new Headers({ Authorization: "Bearer github-secret" }),
        fakeFetch as typeof fetch,
      ),
    ).rejects.toMatchObject({ code: "DOWNLOAD_UPSTREAM_FAILED" });
  });

  it("reports only the safe final upstream status on GitHub failure", async () => {
    const fakeFetch = async (): Promise<Response> =>
      new Response(null, { status: 403 });

    await expect(
      fetchGithubReleaseAsset(
        "https://api.github.com/repos/org/repo/releases/assets/123",
        new Headers({ Authorization: "Bearer TEST_VALUE" }),
        fakeFetch as typeof fetch,
      ),
    ).rejects.toMatchObject({
      code: "DOWNLOAD_UPSTREAM_FAILED",
      status: 502,
      retryable: false,
      details: { upstream_status: 403 },
    });
  });

  it("fails closed after a bounded number of redirects", async () => {
    let calls = 0;
    const fakeFetch = async (): Promise<Response> => {
      calls += 1;
      if (calls <= 5) {
        return new Response(null, {
          status: 302,
          headers: { Location: `https://example.invalid/hop-${calls}` },
        });
      }
      return new Response(new Uint8Array([1]), { status: 200 });
    };

    await expect(
      fetchGithubReleaseAsset(
        "https://api.github.com/repos/org/repo/releases/assets/123",
        new Headers({ Authorization: "Bearer github-secret" }),
        fakeFetch as typeof fetch,
      ),
    ).rejects.toMatchObject({ code: "DOWNLOAD_UPSTREAM_FAILED" });
    expect(calls).toBeLessThanOrEqual(4);
  });
});
