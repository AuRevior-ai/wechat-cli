import { sha256Hex } from "./crypto";
import { ApiError } from "./http";
import type { Env } from "./types";

export type ReleaseDistributionBackend = "github" | "r2";

export interface DistributionRequest {
  backend: ReleaseDistributionBackend;
  objectKey?: string | undefined;
  githubRepository?: string | undefined;
  githubAssetId?: string | undefined;
  expectedSha256: string;
  expectedSize: number;
  range?: string | undefined;
  ifRange?: string | undefined;
}

const GITHUB_ASSET_REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);
const MAX_GITHUB_ASSET_REDIRECTS = 3;
const SHA256_RE = /^[0-9a-f]{64}$/u;
const RELEASE_OBJECT_KEY_RE = /^releases\/(stable|beta)\/[A-Za-z0-9._-]{1,128}\/[0-9a-f]{64}\.zip$/u;

function validSha256(value: string): string {
  const normalized = value.toLowerCase();
  if (!SHA256_RE.test(normalized)) {
    throw new ApiError("RELEASE_STATE_INVALID", "发布包摘要无效。", {
      status: 500,
      retryable: false,
    });
  }
  return normalized;
}

function validExpectedSize(value: number): number {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new ApiError("RELEASE_STATE_INVALID", "发布包大小无效。", {
      status: 500,
      retryable: false,
    });
  }
  return value;
}

export function releaseObjectKey(
  channel: "stable" | "beta",
  releaseId: string,
  packageSha256: string,
): string {
  if (!/^[A-Za-z0-9._-]{1,128}$/u.test(releaseId)) {
    throw new ApiError("INVALID_REQUEST", "发布标识无效。", { status: 400 });
  }
  return `releases/${channel}/${releaseId}/${validSha256(packageSha256)}.zip`;
}

export function githubAssetUrl(repository: string, assetId: string): string {
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/u.test(repository)) {
    throw new ApiError("RELEASE_STATE_INVALID", "发布仓库标识无效。", {
      status: 500,
      retryable: true,
    });
  }
  if (!/^\d+$/u.test(assetId)) {
    throw new ApiError("RELEASE_STATE_INVALID", "发布资源标识无效。", {
      status: 500,
      retryable: true,
    });
  }
  return `https://api.github.com/repos/${repository}/releases/assets/${assetId}`;
}

export async function fetchGithubReleaseAsset(
  initialUrl: string,
  initialHeaders: Headers,
  fetcher: typeof fetch = fetch,
): Promise<Response> {
  let current: URL;
  try {
    current = new URL(initialUrl);
  } catch (error) {
    throw new ApiError("DOWNLOAD_UPSTREAM_FAILED", "GitHub 发布资源地址无效。", {
      status: 502,
      retryable: false,
      cause: error,
    });
  }
  if (current.protocol !== "https:" || current.hostname !== "api.github.com") {
    throw new ApiError("DOWNLOAD_UPSTREAM_FAILED", "GitHub 发布资源地址不受信任。", {
      status: 502,
      retryable: false,
    });
  }

  let headers = new Headers(initialHeaders);
  for (let redirects = 0; ; redirects += 1) {
    const upstream = await fetcher(current.toString(), {
      headers,
      redirect: "manual",
    });
    if (!GITHUB_ASSET_REDIRECT_STATUSES.has(upstream.status)) {
      if (upstream.status === 200 || upstream.status === 206) {
        return upstream;
      }
      console.error(
        JSON.stringify({
          level: "error",
          event: "github_release_asset_upstream_failed",
          upstream_status: upstream.status,
        }),
      );
      throw new ApiError("DOWNLOAD_UPSTREAM_FAILED", "发布资源下载失败。", {
        status: upstream.status === 404 ? 404 : 502,
        retryable: upstream.status >= 500 || upstream.status === 429,
        details: { upstream_status: upstream.status },
      });
    }
    if (redirects >= MAX_GITHUB_ASSET_REDIRECTS) {
      throw new ApiError("DOWNLOAD_UPSTREAM_FAILED", "GitHub 发布资源重定向次数过多。", {
        status: 502,
        retryable: false,
      });
    }
    const location = upstream.headers.get("Location");
    if (location === null) {
      throw new ApiError("DOWNLOAD_UPSTREAM_FAILED", "GitHub 发布资源重定向缺少地址。", {
        status: 502,
        retryable: false,
      });
    }
    let next: URL;
    try {
      next = new URL(location, current);
    } catch (error) {
      throw new ApiError("DOWNLOAD_UPSTREAM_FAILED", "GitHub 发布资源重定向地址无效。", {
        status: 502,
        retryable: false,
        cause: error,
      });
    }
    if (next.protocol !== "https:" || next.username || next.password) {
      throw new ApiError("DOWNLOAD_UPSTREAM_FAILED", "GitHub 发布资源重定向不受信任。", {
        status: 502,
        retryable: false,
      });
    }
    headers = new Headers(headers);
    headers.delete("Authorization");
    current = next;
  }
}

export async function prepareR2ReleasePackage(
  env: Env,
  request: {
    channel: "stable" | "beta";
    releaseId: string;
    packageSha256: string;
    bytes: ArrayBuffer;
  },
): Promise<{
  distribution_backend: "r2";
  distribution_object_key: string;
  package_sha256: string;
  package_size: number;
  ready: true;
}> {
  const packageSha256 = validSha256(request.packageSha256);
  const packageSize = validExpectedSize(request.bytes.byteLength);
  const actualSha256 = await sha256Hex(request.bytes);
  if (actualSha256 !== packageSha256) {
    throw new ApiError("UPDATE_HASH_MISMATCH", "发布包摘要与实际字节不一致。", {
      status: 409,
      retryable: false,
    });
  }
  const objectKey = releaseObjectKey(
    request.channel,
    request.releaseId,
    packageSha256,
  );
  const existing = await env.RELEASES.head(objectKey);
  if (existing !== null) {
    if (
      existing.size !== packageSize ||
      existing.customMetadata?.sha256?.toLowerCase() !== packageSha256
    ) {
      throw new ApiError("RELEASE_OBJECT_CONFLICT", "R2 发布对象已存在但内容元数据不一致。", {
        status: 409,
        retryable: false,
      });
    }
  } else {
    await env.RELEASES.put(objectKey, request.bytes, {
      sha256: packageSha256,
      httpMetadata: { contentType: "application/zip" },
      customMetadata: {
        sha256: packageSha256,
        release_id: request.releaseId,
        channel: request.channel,
      },
    });
  }
  await assertR2ReleaseReady(env, objectKey, packageSha256, packageSize);
  return {
    distribution_backend: "r2",
    distribution_object_key: objectKey,
    package_sha256: packageSha256,
    package_size: packageSize,
    ready: true,
  };
}

export async function assertR2ReleaseReady(
  env: Env,
  objectKey: string,
  expectedSha256: string,
  expectedSize: number,
): Promise<void> {
  if (!RELEASE_OBJECT_KEY_RE.test(objectKey)) {
    throw new ApiError("RELEASE_STATE_INVALID", "R2 发布对象标识无效。", {
      status: 500,
      retryable: false,
    });
  }
  const sha256 = validSha256(expectedSha256);
  const size = validExpectedSize(expectedSize);
  const object = await env.RELEASES.head(objectKey);
  if (object === null) {
    throw new ApiError("RELEASE_STATE_INVALID", "R2 发布对象不存在。", {
      status: 500,
      retryable: true,
    });
  }
  if (
    object.size !== size ||
    object.customMetadata?.sha256?.toLowerCase() !== sha256
  ) {
    throw new ApiError("RELEASE_STATE_INVALID", "R2 发布对象与签名发布元数据不一致。", {
      status: 500,
      retryable: false,
    });
  }
}

function r2Response(
  object: R2ObjectBody,
  totalSize: number,
  rangeRequested: boolean,
): Response {
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("ETag", object.httpEtag);
  let status = 200;
  if (
    rangeRequested &&
    object.range !== undefined &&
    "offset" in object.range &&
    typeof object.range.offset === "number" &&
    "length" in object.range &&
    typeof object.range.length === "number"
  ) {
    const start = object.range.offset;
    const length = object.range.length;
    const end = start + length - 1;
    headers.set("Content-Range", `bytes ${start}-${end}/${totalSize}`);
    headers.set("Content-Length", String(length));
    status = 206;
  } else {
    headers.set("Content-Length", String(totalSize));
  }
  return new Response(object.body, { status, headers });
}

async function fetchR2ReleasePackage(
  env: Env,
  request: DistributionRequest,
): Promise<Response> {
  const objectKey = request.objectKey;
  if (objectKey === undefined) {
    throw new ApiError("RELEASE_STATE_INVALID", "R2 发布对象标识缺失。", {
      status: 500,
      retryable: false,
    });
  }
  if (!RELEASE_OBJECT_KEY_RE.test(objectKey)) {
    throw new ApiError("RELEASE_STATE_INVALID", "R2 发布对象标识无效。", {
      status: 500,
      retryable: false,
    });
  }
  const sha256 = validSha256(request.expectedSha256);
  const expectedSize = validExpectedSize(request.expectedSize);
  const rangeHeaders = new Headers();
  if (request.range !== undefined) rangeHeaders.set("Range", request.range);
  if (request.ifRange !== undefined) rangeHeaders.set("If-Range", request.ifRange);
  const object = await env.RELEASES.get(
    objectKey,
    rangeHeaders.has("Range") ? { range: rangeHeaders } : undefined,
  );
  if (object === null) {
    throw new ApiError("DOWNLOAD_UPSTREAM_FAILED", "发布资源不存在。", {
      status: 404,
      retryable: false,
    });
  }
  if (
    object.size !== expectedSize ||
    object.customMetadata?.sha256?.toLowerCase() !== sha256
  ) {
    throw new ApiError("RELEASE_STATE_INVALID", "R2 发布对象与发布元数据不一致。", {
      status: 500,
      retryable: false,
    });
  }
  return r2Response(object, expectedSize, request.range !== undefined);
}

export async function fetchReleasePackage(
  env: Env,
  request: DistributionRequest,
  fetcher: typeof fetch = fetch,
): Promise<Response> {
  if (request.backend === "r2") {
    return fetchR2ReleasePackage(env, request);
  }
  if (request.backend !== "github") {
    throw new ApiError("RELEASE_STATE_INVALID", "发布分发后端无效。", {
      status: 500,
      retryable: false,
    });
  }
  if (env.ENVIRONMENT === "production") {
    throw new ApiError("RELEASE_STATE_INVALID", "生产环境禁止 GitHub runtime 分发后端。", {
      status: 500,
      retryable: false,
    });
  }
  if (request.githubRepository === undefined || request.githubAssetId === undefined) {
    throw new ApiError("RELEASE_STATE_INVALID", "GitHub 发布资源元数据缺失。", {
      status: 500,
      retryable: false,
    });
  }
  validSha256(request.expectedSha256);
  validExpectedSize(request.expectedSize);
  const headers = new Headers({
    Accept: "application/octet-stream",
    Authorization: `Bearer ${env.GITHUB_RELEASE_READ_TOKEN}`,
    "User-Agent": "wechat-cli-license-update-worker",
    "X-GitHub-Api-Version": "2022-11-28",
  });
  if (request.range !== undefined) headers.set("Range", request.range);
  if (request.ifRange !== undefined) headers.set("If-Range", request.ifRange);
  return fetchGithubReleaseAsset(
    githubAssetUrl(request.githubRepository, request.githubAssetId),
    headers,
    fetcher,
  );
}
