import type { Hono } from "hono";

import { authenticateDevice } from "./auth";
import {
  bytesToBase64,
  constantTimeEqual,
  createDownloadTicket,
  hmacSha256Hex,
  parseDownloadTicket,
  rolloutBucket,
} from "./crypto";
import { ApiError, readJsonObject, requiredString } from "./http";
import { compareSemanticVersions, parseSemanticVersion } from "./semver";
import { addSeconds, enforceRateLimit, isoNow, writeAudit } from "./service";
import type { Env, ReleaseRow } from "./types";

interface WorkerVariables {
  requestId: string;
}

type WorkerApp = Hono<{ Bindings: Env; Variables: WorkerVariables }>;

export function d1BlobBytes(
  value: unknown,
  field: string,
): Uint8Array<ArrayBuffer> {
  if (value instanceof ArrayBuffer) {
    return new Uint8Array(value);
  }
  if (ArrayBuffer.isView(value)) {
    const source = new Uint8Array(
      value.buffer,
      value.byteOffset,
      value.byteLength,
    );
    const copy: Uint8Array<ArrayBuffer> = new Uint8Array(source.byteLength);
    copy.set(source);
    return copy;
  }
  if (
    Array.isArray(value) &&
    value.every(
      (item) => Number.isInteger(item) && Number(item) >= 0 && Number(item) <= 255,
    )
  ) {
    return Uint8Array.from(value as number[]);
  }
  throw new ApiError("RELEASE_STATE_INVALID", `${field} 不是二进制数据。`, {
    status: 500,
    retryable: true,
  });
}

function releaseFromRow(row: Record<string, unknown>): ReleaseRow {
  return {
    id: String(row.id),
    version: String(row.version),
    channel: row.channel as ReleaseRow["channel"],
    manifest_content: d1BlobBytes(row.manifest_content, "manifest_content").buffer,
    manifest_signature: d1BlobBytes(
      row.manifest_signature,
      "manifest_signature",
    ).buffer,
    manifest_sha256: String(row.manifest_sha256),
    package_sha256: String(row.package_sha256),
    package_size: Number(row.package_size),
    github_repository: String(row.github_repository),
    github_release_id: String(row.github_release_id),
    github_asset_id: String(row.github_asset_id),
    github_asset_name: String(row.github_asset_name),
    rollout_percentage: Number(row.rollout_percentage),
    rollout_seed: String(row.rollout_seed),
    paused: Number(row.paused),
    enabled: Number(row.enabled),
    published_at: String(row.published_at),
    created_at: String(row.created_at),
  };
}

function stringArray(value: unknown, name: string, maximum = 32): string[] {
  if (!Array.isArray(value) || value.length > maximum) {
    throw new ApiError("INVALID_REQUEST", `${name} 必须是有限数组。`, {
      status: 400,
    });
  }
  const result: string[] = [];
  for (const item of value) {
    if (typeof item !== "string") {
      throw new ApiError("INVALID_REQUEST", `${name} 包含无效值。`, {
        status: 400,
      });
    }
    try {
      parseSemanticVersion(item);
    } catch (error) {
      throw new ApiError("INVALID_REQUEST", `${name} 包含无效版本。`, {
        status: 400,
        cause: error,
      });
    }
    result.push(item);
  }
  return result;
}

function validTargetValue(
  request: Record<string, unknown>,
  name: string,
  allowed: readonly string[],
): string {
  const value = requiredString(request, name, { maximum: 64 });
  if (!allowed.includes(value)) {
    throw new ApiError("INVALID_REQUEST", `${name} 不受支持。`, { status: 400 });
  }
  return value;
}

async function selectRelease(
  env: Env,
  options: {
    channel: string;
    currentVersion: string;
    failedVersions: Set<string>;
    licenseId: string;
    deviceId: string;
  },
): Promise<ReleaseRow | null> {
  const rows = await env.DB.prepare(
    `SELECT id, version, channel, manifest_content, manifest_signature,
            manifest_sha256, package_sha256, package_size,
            github_repository, github_release_id, github_asset_id,
            github_asset_name, rollout_percentage, rollout_seed,
            paused, enabled, published_at, created_at
       FROM releases
      WHERE channel = ? AND enabled = 1
      ORDER BY published_at DESC
      LIMIT 20`,
  )
    .bind(options.channel)
    .all<Record<string, unknown>>();
  for (const row of rows.results) {
    const release = releaseFromRow(row);
    try {
      if (compareSemanticVersions(release.version, options.currentVersion) <= 0) {
        continue;
      }
    } catch (error) {
      throw new ApiError("RELEASE_STATE_INVALID", "发布版本格式无效。", {
        status: 500,
        retryable: true,
        cause: error,
      });
    }
    if (options.failedVersions.has(release.version) || release.paused !== 0) {
      continue;
    }
    if (release.rollout_percentage <= 0) {
      continue;
    }
    if (release.rollout_percentage < 100) {
      const bucket = await rolloutBucket(
        release.rollout_seed,
        options.licenseId,
        options.deviceId,
      );
      if (bucket >= release.rollout_percentage) {
        continue;
      }
    }
    return release;
  }
  return null;
}

function downloadAuthorization(request: Request): string {
  const header = request.headers.get("Authorization");
  const match = header === null ? null : /^Download\s+(.+)$/iu.exec(header.trim());
  if (match === null || match[1] === undefined) {
    throw new ApiError("DOWNLOAD_NOT_AUTHORIZED", "缺少下载票据。", {
      status: 401,
    });
  }
  return match[1];
}

function githubAssetUrl(repository: string, assetId: string): string {
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

export function registerUpdateRoutes(app: WorkerApp): void {
  app.post("/v1/updates/check", async (c) => {
    const authenticated = await authenticateDevice(c);
    await enforceRateLimit(c, {
      name: "update-check",
      maximum: 12,
      windowSeconds: 60,
      identity: authenticated.device.id,
    });
    const request = await readJsonObject(c.req.raw);
    const currentVersion = requiredString(request, "current_version", {
      maximum: 64,
    });
    const launcherVersion = requiredString(request, "launcher_version", {
      maximum: 64,
    });
    try {
      parseSemanticVersion(currentVersion);
      parseSemanticVersion(launcherVersion);
    } catch (error) {
      throw new ApiError("INVALID_REQUEST", "客户端版本格式无效。", {
        status: 400,
        cause: error,
      });
    }
    const channel = validTargetValue(request, "channel", ["stable", "beta"]);
    validTargetValue(request, "platform", ["windows"]);
    validTargetValue(request, "architecture", ["x86_64", "arm64"]);
    const product = requiredString(request, "product", { maximum: 64 });
    if (product !== "wechat-cli-web") {
      throw new ApiError("UPDATE_PLATFORM_MISMATCH", "产品标识不匹配。", {
        status: 409,
      });
    }
    const deviceId = requiredString(request, "device_id", { maximum: 160 });
    if (deviceId !== authenticated.device.id) {
      throw new ApiError("INVALID_DEVICE_TOKEN", "设备标识与令牌不匹配。", {
        status: 401,
      });
    }
    const failedVersions = new Set(
      stringArray(request.failed_versions ?? [], "failed_versions"),
    );
    const release = await selectRelease(c.env, {
      channel,
      currentVersion,
      failedVersions,
      licenseId: authenticated.license.id,
      deviceId: authenticated.device.id,
    });
    const checkedAt = isoNow();
    if (release === null) {
      return c.json({
        update_available: false,
        current_version: currentVersion,
        channel,
        checked_at: checkedAt,
      });
    }

    const ticket = createDownloadTicket();
    const ticketDigest = await hmacSha256Hex(
      c.env.DOWNLOAD_TICKET_SECRET,
      ticket.secret,
    );
    const expiresAt = isoNow(addSeconds(new Date(), 10 * 60));
    await c.env.DB.prepare(
      `INSERT INTO download_tickets (
         id, ticket_digest, release_id, license_id, device_id,
         expected_sha256, expected_size, expires_at, created_at
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
      .bind(
        ticket.ticketId,
        ticketDigest,
        release.id,
        authenticated.license.id,
        authenticated.device.id,
        release.package_sha256,
        release.package_size,
        expiresAt,
        checkedAt,
      )
      .run();
    await writeAudit(c.env, {
      actorType: "device",
      actorId: authenticated.device.id,
      action: "update.check",
      targetType: "release",
      targetId: release.id,
      result: "update_available",
      requestId: c.get("requestId"),
      metadata: {
        current_version: currentVersion,
        target_version: release.version,
        launcher_version: launcherVersion,
        channel,
      },
    });
    return c.json({
      update_available: true,
      manifest: {
        content_base64: bytesToBase64(release.manifest_content),
        signature_base64: bytesToBase64(release.manifest_signature),
      },
      download_ticket: ticket.value,
      download_ticket_expires_at: expiresAt,
      checked_at: checkedAt,
    });
  });

  app.get("/v1/updates/download", async (c) => {
    const rawTicket = downloadAuthorization(c.req.raw);
    let ticket: ReturnType<typeof parseDownloadTicket>;
    try {
      ticket = parseDownloadTicket(rawTicket);
    } catch (error) {
      throw new ApiError("DOWNLOAD_NOT_AUTHORIZED", "下载票据无效。", {
        status: 401,
        cause: error,
      });
    }
    const row = await c.env.DB.prepare(
      `SELECT
         t.id, t.ticket_digest, t.release_id, t.license_id, t.device_id,
         t.expected_sha256, t.expected_size, t.expires_at, t.revoked_at,
         r.github_repository, r.github_asset_id, r.github_asset_name,
         r.package_sha256, r.package_size, r.enabled, r.paused,
         l.status AS license_status, d.status AS device_status
       FROM download_tickets t
       JOIN releases r ON r.id = t.release_id
       JOIN licenses l ON l.id = t.license_id
       JOIN devices d ON d.id = t.device_id
       WHERE t.id = ?
       LIMIT 1`,
    )
      .bind(ticket.ticketId)
      .first<Record<string, unknown>>();
    if (row === null) {
      throw new ApiError("DOWNLOAD_NOT_AUTHORIZED", "下载票据无效。", {
        status: 401,
      });
    }
    const expectedDigest = await hmacSha256Hex(
      c.env.DOWNLOAD_TICKET_SECRET,
      ticket.secret,
    );
    if (!constantTimeEqual(expectedDigest, String(row.ticket_digest))) {
      throw new ApiError("DOWNLOAD_NOT_AUTHORIZED", "下载票据无效。", {
        status: 401,
      });
    }
    const now = isoNow();
    if (row.revoked_at !== null || String(row.expires_at) <= now) {
      throw new ApiError("DOWNLOAD_TICKET_EXPIRED", "下载票据已过期。", {
        status: 401,
      });
    }
    if (row.license_status !== "active" || row.device_status !== "active") {
      throw new ApiError("DOWNLOAD_NOT_AUTHORIZED", "许可证或设备当前不可下载。", {
        status: 403,
      });
    }
    if (Number(row.enabled) !== 1 || Number(row.paused) !== 0) {
      throw new ApiError("UPDATE_PAUSED", "该发布已暂停。", { status: 403 });
    }
    if (
      String(row.expected_sha256) !== String(row.package_sha256) ||
      Number(row.expected_size) !== Number(row.package_size)
    ) {
      throw new ApiError("RELEASE_STATE_INVALID", "下载票据与发布元数据不一致。", {
        status: 500,
        retryable: true,
      });
    }

    const headers = new Headers({
      Accept: "application/octet-stream",
      Authorization: `Bearer ${c.env.GITHUB_RELEASE_READ_TOKEN}`,
      "User-Agent": "wechat-cli-license-update-worker",
      "X-GitHub-Api-Version": "2022-11-28",
    });
    const range = c.req.header("Range");
    const ifRange = c.req.header("If-Range");
    if (range !== undefined) headers.set("Range", range);
    if (ifRange !== undefined) headers.set("If-Range", ifRange);
    const upstream = await fetch(
      githubAssetUrl(String(row.github_repository), String(row.github_asset_id)),
      { headers, redirect: "follow" },
    );
    if (upstream.status !== 200 && upstream.status !== 206) {
      throw new ApiError("DOWNLOAD_UPSTREAM_FAILED", "发布资源下载失败。", {
        status: upstream.status === 404 ? 404 : 502,
        retryable: upstream.status >= 500 || upstream.status === 429,
      });
    }
    const responseHeaders = new Headers();
    for (const name of [
      "Content-Length",
      "Content-Range",
      "Content-Type",
      "ETag",
      "Last-Modified",
      "Accept-Ranges",
    ]) {
      const value = upstream.headers.get(name);
      if (value !== null) responseHeaders.set(name, value);
    }
    responseHeaders.set(
      "Content-Disposition",
      `attachment; filename="${String(row.github_asset_name).replaceAll('"', "")}"`,
    );
    responseHeaders.set("Cache-Control", "private, no-store");
    c.executionCtx.waitUntil(
      Promise.all([
        c.env.DB.prepare(
          "UPDATE download_tickets SET last_used_at = ? WHERE id = ?",
        )
          .bind(now, ticket.ticketId)
          .run(),
        writeAudit(c.env, {
          actorType: "device",
          actorId: String(row.device_id),
          action: "update.download",
          targetType: "release",
          targetId: String(row.release_id),
          result: upstream.status === 206 ? "partial" : "success",
          requestId: c.get("requestId"),
          metadata: {
            range_requested: range !== undefined,
            upstream_status: upstream.status,
          },
        }),
      ]).then(() => undefined),
    );
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  });
}
