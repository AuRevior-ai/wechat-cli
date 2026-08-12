import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../src/http";
import type { Env } from "../src/types";

interface DistributionModule {
  fetchReleasePackage?: (
    env: Env,
    request: {
      backend: "github" | "r2";
      objectKey?: string;
      githubRepository?: string;
      githubAssetId?: string;
      expectedSha256: string;
      expectedSize: number;
      range?: string;
      ifRange?: string;
    },
    fetcher?: typeof fetch,
  ) => Promise<Response>;
  assertR2ReleaseReady?: (
    env: Env,
    objectKey: string,
    expectedSha256: string,
    expectedSize: number,
  ) => Promise<void>;
  prepareR2ReleasePackage?: (
    env: Env,
    request: {
      channel: "stable" | "beta";
      releaseId: string;
      packageSha256: string;
      bytes: ArrayBuffer;
    },
  ) => Promise<{
    distribution_backend: "r2";
    distribution_object_key: string;
    package_sha256: string;
    package_size: number;
    ready: true;
  }>;
}

async function loadDistributionModule(): Promise<DistributionModule> {
  try {
    const modulePath = "../src/" + "distribution";
    return (await import(modulePath)) as DistributionModule;
  } catch {
    return {};
  }
}

function fakeR2Object(options: {
  key: string;
  bytes: Uint8Array;
  sha256: string;
  size?: number;
  range?: { offset: number; length: number };
}): R2ObjectBody {
  const payload = options.bytes;
  return {
    key: options.key,
    version: "v1",
    size: options.size ?? payload.byteLength,
    etag: "etag",
    httpEtag: '"etag"',
    checksums: {} as R2Checksums,
    uploaded: new Date("2026-08-12T00:00:00Z"),
    customMetadata: { sha256: options.sha256 },
    range: options.range,
    storageClass: "Standard",
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(payload);
        controller.close();
      },
    }),
    bodyUsed: false,
    writeHttpMetadata() {},
    async arrayBuffer() {
      return payload.slice().buffer;
    },
    async bytes() {
      return payload.slice();
    },
    async text() {
      return new TextDecoder().decode(payload);
    },
    async json<T>() {
      return JSON.parse(new TextDecoder().decode(payload)) as T;
    },
    async blob() {
      return new Blob([payload.slice().buffer as ArrayBuffer]);
    },
  } as R2ObjectBody;
}

describe("release distribution backend", () => {
  it("exports the distribution contract", async () => {
    const module = await loadDistributionModule();
    expect(module.fetchReleasePackage).toBeTypeOf("function");
    expect(module.assertR2ReleaseReady).toBeTypeOf("function");
  });

  it("prepares an exact R2 object under a server-generated key", async () => {
    const module = await loadDistributionModule();
    expect(module.prepareR2ReleasePackage).toBeTypeOf("function");
    const sha = "039058c6f2c0cb492c533b0a4d14ef77cc0f78abccced5287d84a1a2011cfb81";
    let stored: R2Object | null = null;
    const put = vi.fn(async (key: string, _value: unknown, options?: R2PutOptions) => {
      stored = {
        key,
        version: "v1",
        size: 3,
        etag: "etag",
        httpEtag: '"etag"',
        checksums: {} as R2Checksums,
        uploaded: new Date("2026-08-12T00:00:00Z"),
        customMetadata: options?.customMetadata,
        storageClass: "Standard",
        writeHttpMetadata() {},
      } as R2Object;
      return stored;
    });
    const bucket = {
      head: vi.fn(async () => stored),
      put,
    } as unknown as R2Bucket;
    const env = { ENVIRONMENT: "staging", RELEASES: bucket } as Env;

    const result = await module.prepareR2ReleasePackage!(env, {
      channel: "stable",
      releaseId: "rel_051",
      packageSha256: sha,
      bytes: Uint8Array.from([1, 2, 3]).buffer,
    });

    expect(result.ready).toBe(true);
    expect(result.package_size).toBe(3);
    expect(result.distribution_object_key).toBe(`releases/stable/rel_051/${sha}.zip`);
    expect(put).toHaveBeenCalledTimes(1);
    const putOptions = put.mock.calls[0]?.[2] as R2PutOptions | undefined;
    expect(putOptions?.customMetadata?.sha256).toBe(sha);
    expect(putOptions?.sha256).toBe(sha);
    expect((putOptions?.httpMetadata as R2HTTPMetadata | undefined)?.contentType).toBe(
      "application/zip",
    );
  });

  it("serves an R2 object without making any outbound fetch", async () => {
    const module = await loadDistributionModule();
    expect(module.fetchReleasePackage).toBeTypeOf("function");
    const bytes = Uint8Array.from([1, 2, 3]);
    const sha = "a".repeat(64);
    const objectKey = `releases/stable/rel/${sha}.zip`;
    const get = vi.fn(async () => fakeR2Object({ key: objectKey, bytes, sha256: sha }));
    const env = {
      ENVIRONMENT: "staging",
      RELEASES: { get } as unknown as R2Bucket,
    } as Env;
    const outbound = vi.fn(async () => new Response(null, { status: 500 }));

    const response = await module.fetchReleasePackage!(
      env,
      {
        backend: "r2",
        objectKey,
        expectedSha256: sha,
        expectedSize: 3,
      },
      outbound as typeof fetch,
    );

    expect(response.status).toBe(200);
    expect([...new Uint8Array(await response.arrayBuffer())]).toEqual([1, 2, 3]);
    expect(outbound).not.toHaveBeenCalled();
    expect(get).toHaveBeenCalledTimes(1);
  });

  it("fails closed when R2 size or hash metadata does not match", async () => {
    const module = await loadDistributionModule();
    expect(module.assertR2ReleaseReady).toBeTypeOf("function");
    const env = {
      ENVIRONMENT: "staging",
      RELEASES: {
        head: async () => ({
          key: `releases/stable/rel/${"a".repeat(64)}.zip`,
          size: 2,
          customMetadata: { sha256: "b".repeat(64) },
        }),
      } as unknown as R2Bucket,
    } as Env;

    await expect(
      module.assertR2ReleaseReady!(
        env,
        `releases/stable/rel/${"a".repeat(64)}.zip`,
        "a".repeat(64),
        3,
      ),
    ).rejects.toMatchObject({
      code: "RELEASE_STATE_INVALID",
    } satisfies Partial<ApiError>);
  });

  it("preserves byte-range semantics for R2 downloads", async () => {
    const module = await loadDistributionModule();
    expect(module.fetchReleasePackage).toBeTypeOf("function");
    const fullSha = "a".repeat(64);
    const objectKey = `releases/stable/rel/${fullSha}.zip`;
    const ranged = Uint8Array.from([2, 3]);
    const get = vi.fn(async (_key: string, options?: R2GetOptions) => {
      const headers = options?.range as Headers;
      expect(headers.get("Range")).toBe("bytes=1-2");
      return fakeR2Object({
        key: objectKey,
        bytes: ranged,
        sha256: fullSha,
        size: 3,
        range: { offset: 1, length: 2 },
      });
    });
    const env = {
      ENVIRONMENT: "staging",
      RELEASES: { get } as unknown as R2Bucket,
    } as Env;

    const response = await module.fetchReleasePackage!(env, {
      backend: "r2",
      objectKey,
      expectedSha256: fullSha,
      expectedSize: 3,
      range: "bytes=1-2",
    });

    expect(response.status).toBe(206);
    expect(response.headers.get("Content-Range")).toBe("bytes 1-2/3");
    expect(response.headers.get("Content-Length")).toBe("2");
    expect([...new Uint8Array(await response.arrayBuffer())]).toEqual([2, 3]);
  });

  it("keeps legacy GitHub-backed rows working outside production", async () => {
    const module = await loadDistributionModule();
    expect(module.fetchReleasePackage).toBeTypeOf("function");
    const outbound = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      expect(headers.get("Authorization")).toBe("Bearer github-read-token");
      expect(headers.get("X-GitHub-Api-Version")).toBe("2022-11-28");
      return new Response(Uint8Array.from([7, 8, 9]), { status: 200 });
    });
    const env = {
      ENVIRONMENT: "staging",
      GITHUB_RELEASE_READ_TOKEN: "github-read-token",
    } as Env;

    const response = await module.fetchReleasePackage!(
      env,
      {
        backend: "github",
        githubRepository: "org/repo",
        githubAssetId: "123",
        expectedSha256: "a".repeat(64),
        expectedSize: 3,
      },
      outbound as typeof fetch,
    );

    expect(response.status).toBe(200);
    expect(outbound).toHaveBeenCalledTimes(1);
    expect(String(outbound.mock.calls[0]?.[0])).toBe(
      "https://api.github.com/repos/org/repo/releases/assets/123",
    );
  });

  it("rejects the legacy GitHub runtime backend in production", async () => {
    const module = await loadDistributionModule();
    expect(module.fetchReleasePackage).toBeTypeOf("function");
    const env = { ENVIRONMENT: "production" } as Env;

    await expect(
      module.fetchReleasePackage!(env, {
        backend: "github",
        githubRepository: "org/repo",
        githubAssetId: "123",
        expectedSha256: "a".repeat(64),
        expectedSize: 3,
      }),
    ).rejects.toMatchObject({ code: "RELEASE_STATE_INVALID" } satisfies Partial<ApiError>);
  });
});
