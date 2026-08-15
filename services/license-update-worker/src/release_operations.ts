import { base64ToBytes, randomId, sha256Hex } from "./crypto";
import { assertR2ReleaseReady, prepareR2ReleasePackage } from "./distribution";
import {
  ApiError,
  optionalString,
  readJsonObject,
  requiredInteger,
  requiredString,
} from "./http";
import { parseSemanticVersion } from "./semver";
import { isoNow, runIdempotent, writeAudit } from "./service";
import type { AuthenticatedAdmin, Env } from "./types";

export interface ReleaseOperationActor {
  actorType: "admin" | "automation";
  actorId: string;
  requestId: string;
}

function parseBoolean(value: unknown, name: string): boolean | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "boolean") {
    throw new ApiError("INVALID_REQUEST", `${name} 必须是布尔值。`, { status: 400 });
  }
  return value;
}

function idempotencyScope(actor: ReleaseOperationActor, action: string): string {
  return `${actor.actorType}-release-${action}:${actor.actorId}`;
}

export async function assertReleaseVersionImmutable(
  env: Env,
  channel: "stable" | "beta",
  version: string,
  manifestSha256: string,
): Promise<void> {
  const existing = await env.DB.prepare(
    `SELECT id, manifest_sha256
       FROM releases
      WHERE channel = ? AND version = ?
      ORDER BY created_at ASC
      LIMIT 1`,
  )
    .bind(channel, version)
    .first<Record<string, unknown>>();
  if (
    existing !== null &&
    String(existing.manifest_sha256).toLowerCase() !== manifestSha256.toLowerCase()
  ) {
    throw new ApiError(
      "RELEASE_VERSION_IMMUTABLE",
      "同一发布通道与版本不能替换为不同清单。",
      { status: 409, retryable: false },
    );
  }
}

export async function prepareReleasePackageOperation(
  env: Env,
  request: Request,
  releaseId: string,
  actor: ReleaseOperationActor,
): Promise<{ status: number; body: Record<string, unknown> }> {
  if (!/^[A-Za-z0-9._-]{1,128}$/u.test(releaseId)) {
    throw new ApiError("INVALID_REQUEST", "发布标识无效。", { status: 400 });
  }
  const channel = request.headers.get("X-Release-Channel");
  if (channel !== "stable" && channel !== "beta") {
    throw new ApiError("INVALID_REQUEST", "发布通道无效。", { status: 400 });
  }
  const packageSha256 = request.headers.get("X-Package-Sha256")?.toLowerCase();
  if (packageSha256 === undefined || !/^[0-9a-f]{64}$/u.test(packageSha256)) {
    throw new ApiError("INVALID_REQUEST", "发布包摘要无效。", { status: 400 });
  }
  const nonce = request.headers.get("X-Operation-Nonce");
  if (nonce === null || nonce.length < 8 || nonce.length > 256) {
    throw new ApiError("INVALID_IDEMPOTENCY_KEY", "幂等操作编号格式无效。", {
      status: 400,
    });
  }
  const contentLength = Number(request.headers.get("Content-Length") ?? "");
  const maximumBytes = 64 * 1024 * 1024;
  if (
    !Number.isSafeInteger(contentLength) ||
    contentLength <= 0 ||
    contentLength > maximumBytes
  ) {
    throw new ApiError("INVALID_REQUEST", "发布包大小无效或超过当前上传上限。", {
      status: 400,
    });
  }
  const response = await runIdempotent(env, {
    scope: idempotencyScope(actor, "upload"),
    key: nonce,
    request: { releaseId, channel, packageSha256, contentLength },
    operation: async () => {
      const body = await request.arrayBuffer();
      if (body.byteLength !== contentLength) {
        throw new ApiError("INVALID_REQUEST", "发布包实际大小与 Content-Length 不一致。", {
          status: 400,
        });
      }
      const prepared = await prepareR2ReleasePackage(env, {
        channel,
        releaseId,
        packageSha256,
        bytes: body,
      });
      await writeAudit(env, {
        actorType: actor.actorType,
        actorId: actor.actorId,
        action: "release.package_ready",
        targetType: "release",
        targetId: releaseId,
        result: "success",
        requestId: actor.requestId,
        metadata: {
          channel,
          distribution_backend: "r2",
          package_sha256: packageSha256,
          package_size: contentLength,
        },
      });
      return {
        body: {
          release_id: releaseId,
          distribution_backend: "r2",
          distribution_object_key: prepared.distribution_object_key,
          package_sha256: prepared.package_sha256,
          package_size: prepared.package_size,
          ready: prepared.ready,
        },
      };
    },
  });
  return { status: response.status, body: response.body };
}

export async function registerDisabledReleaseOperation(
  env: Env,
  request: Request,
  actor: ReleaseOperationActor,
): Promise<{ status: number; body: Record<string, unknown> }> {
  const value = await readJsonObject(request, { maximumBytes: 2 * 1024 * 1024 });
  const releaseId = requiredString(value, "release_id", { maximum: 128 });
  const version = requiredString(value, "version", { maximum: 64 });
  try {
    parseSemanticVersion(version);
  } catch (error) {
    throw new ApiError("INVALID_REQUEST", "发布版本无效。", { status: 400, cause: error });
  }
  const channel = requiredString(value, "channel", { maximum: 16 });
  if (channel !== "stable" && channel !== "beta") {
    throw new ApiError("INVALID_REQUEST", "发布通道无效。", { status: 400 });
  }
  const manifestContent = base64ToBytes(
    requiredString(value, "manifest_content_base64", { maximum: 1_500_000 }),
  );
  const manifestSignature = base64ToBytes(
    requiredString(value, "manifest_signature_base64", { maximum: 4096 }),
    64,
  );
  const manifestSha256 = requiredString(value, "manifest_sha256", {
    minimum: 64,
    maximum: 64,
    pattern: /^[0-9a-f]{64}$/iu,
  }).toLowerCase();
  if ((await sha256Hex(manifestContent)) !== manifestSha256) {
    throw new ApiError("UPDATE_HASH_MISMATCH", "清单摘要与原始字节不一致。", {
      status: 409,
    });
  }
  const packageSha256 = requiredString(value, "package_sha256", {
    minimum: 64,
    maximum: 64,
    pattern: /^[0-9a-f]{64}$/iu,
  }).toLowerCase();
  const packageSize = requiredInteger(value, "package_size", {
    minimum: 1,
    maximum: 8 * 1024 * 1024 * 1024,
  });
  const repository = requiredString(value, "github_repository", {
    maximum: 256,
    pattern: /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/u,
  });
  const githubReleaseId = requiredString(value, "github_release_id", {
    maximum: 64,
    pattern: /^\d+$/u,
  });
  const githubAssetId = requiredString(value, "github_asset_id", {
    maximum: 64,
    pattern: /^\d+$/u,
  });
  const assetName = requiredString(value, "github_asset_name", { maximum: 256 });
  const distributionBackend =
    value.distribution_backend === undefined
      ? "github"
      : requiredString(value, "distribution_backend", { maximum: 16 });
  if (distributionBackend !== "github" && distributionBackend !== "r2") {
    throw new ApiError("INVALID_REQUEST", "发布分发后端无效。", { status: 400 });
  }
  const distributionObjectKey =
    distributionBackend === "r2"
      ? requiredString(value, "distribution_object_key", { maximum: 512 })
      : null;
  if (distributionBackend === "r2") {
    await assertR2ReleaseReady(env, distributionObjectKey as string, packageSha256, packageSize);
  }
  if (distributionBackend === "github" && env.ENVIRONMENT === "production") {
    throw new ApiError("RELEASE_STATE_INVALID", "生产环境禁止 GitHub runtime 分发后端。", {
      status: 409,
      retryable: false,
    });
  }
  if (
    actor.actorType === "automation" &&
    (value.rollout_percentage !== undefined || value.rollout_seed !== undefined)
  ) {
    throw new ApiError(
      "AUTOMATION_RELEASE_STATE_FORBIDDEN",
      "自动化发布注册不能指定 rollout 状态或分桶种子。",
      { status: 400, retryable: false },
    );
  }
  const rolloutPercentage =
    actor.actorType === "automation"
      ? 0
      : value.rollout_percentage === undefined
        ? 100
        : requiredInteger(value, "rollout_percentage", { minimum: 0, maximum: 100 });
  const rolloutSeed =
    actor.actorType === "automation"
      ? randomId("rollout_", 18)
      : (optionalString(value, "rollout_seed", 256) ?? randomId("rollout_", 18));
  const nonce = requiredString(value, "operation_nonce", { minimum: 8, maximum: 256 });
  const response = await runIdempotent(env, {
    scope: idempotencyScope(actor, "create"),
    key: nonce,
    request: {
      releaseId,
      version,
      channel,
      manifestSha256,
      packageSha256,
      packageSize,
      repository,
      githubReleaseId,
      githubAssetId,
      assetName,
      distributionBackend,
      distributionObjectKey,
      rolloutPercentage,
    },
    operation: async () => {
      await assertReleaseVersionImmutable(env, channel, version, manifestSha256);
      const now = isoNow();
      await env.DB.prepare(
        `INSERT INTO releases (
           id, version, channel, manifest_content, manifest_signature,
           manifest_sha256, package_sha256, package_size,
           github_repository, github_release_id, github_asset_id,
           github_asset_name, distribution_backend, distribution_object_key,
           rollout_percentage, rollout_seed,
           paused, enabled, published_at, created_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)`,
      )
        .bind(
          releaseId,
          version,
          channel,
          manifestContent,
          manifestSignature,
          manifestSha256,
          packageSha256,
          packageSize,
          repository,
          githubReleaseId,
          githubAssetId,
          assetName,
          distributionBackend,
          distributionObjectKey,
          rolloutPercentage,
          rolloutSeed,
          now,
          now,
        )
        .run();
      await writeAudit(env, {
        actorType: actor.actorType,
        actorId: actor.actorId,
        action: "release.register",
        targetType: "release",
        targetId: releaseId,
        result: "success",
        requestId: actor.requestId,
        metadata: {
          version,
          channel,
          distribution_backend: distributionBackend,
          enabled: false,
          paused: true,
        },
      });
      return {
        status: 201,
        body: {
          release_id: releaseId,
          version,
          channel,
          enabled: false,
          paused: true,
          distribution_backend: distributionBackend,
          distribution_object_key: distributionObjectKey,
          rollout_percentage: rolloutPercentage,
          created_at: now,
        },
      };
    },
  });
  return { status: response.status, body: response.body };
}

function releaseRecord(row: Record<string, unknown>): Record<string, unknown> {
  return {
    release_id: String(row.id),
    version: String(row.version),
    channel: String(row.channel),
    manifest_sha256: String(row.manifest_sha256),
    package_sha256: String(row.package_sha256),
    package_size: Number(row.package_size),
    github_repository: String(row.github_repository),
    github_release_id: String(row.github_release_id),
    github_asset_id: String(row.github_asset_id),
    github_asset_name: String(row.github_asset_name),
    distribution_backend: String(row.distribution_backend ?? "github"),
    distribution_object_key:
      row.distribution_object_key === null || row.distribution_object_key === undefined
        ? null
        : String(row.distribution_object_key),
    rollout_percentage: Number(row.rollout_percentage),
    paused: Number(row.paused) === 1,
    enabled: Number(row.enabled) === 1,
    published_at: String(row.published_at),
    created_at: String(row.created_at),
  };
}

export async function listReleaseMetadataOperation(env: Env): Promise<Record<string, unknown>[]> {
  const rows = await env.DB.prepare(
    `SELECT id, version, channel, manifest_sha256, package_sha256,
            package_size, github_repository, github_release_id,
            github_asset_id, github_asset_name, distribution_backend,
            distribution_object_key, rollout_percentage,
            paused, enabled, published_at, created_at
       FROM releases ORDER BY published_at DESC LIMIT 200`,
  ).all<Record<string, unknown>>();
  return rows.results.map(releaseRecord);
}

export function assertHumanReleaseStateAuthority(admin: AuthenticatedAdmin): void {
  if (admin.authMode !== "session") {
    throw new ApiError(
      "RELEASE_STATE_HUMAN_SESSION_REQUIRED",
      "发布状态变更仅允许短期人工管理员会话。",
      { status: 403, retryable: false },
    );
  }
}

export async function updateReleaseStateOperation(
  env: Env,
  request: Request,
  releaseId: string,
  actor: ReleaseOperationActor,
): Promise<{ status: number; body: Record<string, unknown> }> {
  const value = await readJsonObject(request);
  const enabled = parseBoolean(value.enabled, "enabled");
  const paused = parseBoolean(value.paused, "paused");
  const rolloutPercentage =
    value.rollout_percentage === undefined
      ? undefined
      : requiredInteger(value, "rollout_percentage", { minimum: 0, maximum: 100 });
  if (enabled === undefined && paused === undefined && rolloutPercentage === undefined) {
    throw new ApiError("INVALID_REQUEST", "至少需要一个发布状态字段。", { status: 400 });
  }
  const nonce = requiredString(value, "operation_nonce", { minimum: 8, maximum: 256 });
  const response = await runIdempotent(env, {
    scope: idempotencyScope(actor, "update"),
    key: nonce,
    request: { releaseId, enabled, paused, rolloutPercentage },
    operation: async () => {
      if (enabled === true) {
        const release = await env.DB.prepare(
          `SELECT distribution_backend, distribution_object_key,
                  package_sha256, package_size
             FROM releases
            WHERE id = ?
            LIMIT 1`,
        )
          .bind(releaseId)
          .first<Record<string, unknown>>();
        if (release === null) {
          throw new ApiError("RELEASE_NOT_FOUND", "发布不存在。", { status: 404 });
        }
        const backend = String(release.distribution_backend ?? "github");
        if (backend === "r2") {
          if (release.distribution_object_key === null) {
            throw new ApiError("RELEASE_STATE_INVALID", "R2 发布对象标识缺失。", {
              status: 409,
              retryable: false,
            });
          }
          await assertR2ReleaseReady(
            env,
            String(release.distribution_object_key),
            String(release.package_sha256),
            Number(release.package_size),
          );
        } else if (backend === "github" && env.ENVIRONMENT === "production") {
          throw new ApiError("RELEASE_STATE_INVALID", "生产环境禁止 GitHub runtime 分发后端。", {
            status: 409,
            retryable: false,
          });
        }
      }
      const updated = await env.DB.prepare(
        `UPDATE releases
            SET enabled = COALESCE(?, enabled),
                paused = COALESCE(?, paused),
                rollout_percentage = COALESCE(?, rollout_percentage)
          WHERE id = ?`,
      )
        .bind(
          enabled === undefined ? null : enabled ? 1 : 0,
          paused === undefined ? null : paused ? 1 : 0,
          rolloutPercentage ?? null,
          releaseId,
        )
        .run();
      if (Number(updated.meta.changes ?? 0) !== 1) {
        throw new ApiError("RELEASE_NOT_FOUND", "发布不存在。", { status: 404 });
      }
      await writeAudit(env, {
        actorType: actor.actorType,
        actorId: actor.actorId,
        action: "release.update",
        targetType: "release",
        targetId: releaseId,
        result: "success",
        requestId: actor.requestId,
        metadata: { enabled, paused, rollout_percentage: rolloutPercentage },
      });
      return {
        body: {
          ok: true,
          release_id: releaseId,
          ...(enabled === undefined ? {} : { enabled }),
          ...(paused === undefined ? {} : { paused }),
          ...(rolloutPercentage === undefined
            ? {}
            : { rollout_percentage: rolloutPercentage }),
        },
      };
    },
  });
  return { status: response.status, body: response.body };
}
