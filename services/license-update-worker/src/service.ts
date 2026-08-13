import type { Context } from "hono";

import { hmacSha256Hex, randomId, sha256Hex } from "./crypto";
import { ApiError } from "./http";
import { versionedSecretSet } from "./secret_versions";
import type { Env, WorkerVariables } from "./types";

export function isoNow(now = new Date()): string {
  return now.toISOString();
}

export function addSeconds(value: Date, seconds: number): Date {
  return new Date(value.getTime() + seconds * 1000);
}

export function addDays(value: Date, days: number): Date {
  return addSeconds(value, days * 24 * 60 * 60);
}

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(stableValue);
  }
  if (typeof value === "object" && value !== null) {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, stableValue(item)]),
    );
  }
  return value;
}

export function stableJson(value: unknown): string {
  return JSON.stringify(stableValue(value));
}

export async function writeAudit(
  env: Env,
  options: {
    actorType: "admin" | "license" | "device" | "system";
    actorId?: string;
    action: string;
    targetType?: string;
    targetId?: string;
    result: string;
    requestId: string;
    metadata?: Record<string, unknown>;
    createdAt?: string;
  },
): Promise<void> {
  const metadata = options.metadata === undefined ? null : stableJson(options.metadata);
  await env.DB.prepare(
    `INSERT INTO audit_events (
       id, actor_type, actor_id, action, target_type, target_id,
       result, request_id, metadata_json, created_at
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  )
    .bind(
      randomId("audit_"),
      options.actorType,
      options.actorId ?? null,
      options.action,
      options.targetType ?? null,
      options.targetId ?? null,
      options.result,
      options.requestId,
      metadata,
      options.createdAt ?? isoNow(),
    )
    .run();
}

export async function enforceRateLimit(
  c: Context<{ Bindings: Env; Variables: WorkerVariables }, any, any>,
  options: {
    name: string;
    maximum: number;
    windowSeconds: number;
    identity?: string;
  },
): Promise<void> {
  if (!Number.isInteger(options.maximum) || options.maximum < 1) {
    throw new Error("rate limit maximum must be positive");
  }
  if (!Number.isInteger(options.windowSeconds) || options.windowSeconds < 1) {
    throw new Error("rate limit window must be positive");
  }
  const identity =
    options.identity ??
    c.req.header("CF-Connecting-IP") ??
    c.req.header("X-Forwarded-For")?.split(",", 1)[0]?.trim() ??
    "unknown";
  const rateLimitSecret = versionedSecretSet(c.env, "rate-limit-pepper").current();
  const identityDigest = await hmacSha256Hex(
    rateLimitSecret.value,
    `rate-limit\u0000${identity}`,
  );
  const epochSeconds = Math.floor(Date.now() / 1000);
  const windowEpoch =
    Math.floor(epochSeconds / options.windowSeconds) * options.windowSeconds;
  const windowStart = new Date(windowEpoch * 1000).toISOString();
  const expiresAt = new Date(
    (windowEpoch + options.windowSeconds * 2) * 1000,
  ).toISOString();
  const key = `${options.name}:${identityDigest}`;
  const row = await c.env.DB.prepare(
    `INSERT INTO rate_limit_windows (key, window_start, count, expires_at)
     VALUES (?, ?, 1, ?)
     ON CONFLICT(key) DO UPDATE SET
       count = CASE
         WHEN rate_limit_windows.window_start = excluded.window_start
         THEN rate_limit_windows.count + 1
         ELSE 1
       END,
       window_start = excluded.window_start,
       expires_at = excluded.expires_at
     RETURNING count`,
  )
    .bind(key, windowStart, expiresAt)
    .first<{ count: number }>();
  const count = Number(row?.count ?? options.maximum + 1);
  if (count > options.maximum) {
    throw new ApiError("RATE_LIMITED", "请求过于频繁，请稍后重试。", {
      status: 429,
      retryable: true,
      details: { retry_after_seconds: options.windowSeconds },
    });
  }
}

export interface StoredResponse<T extends Record<string, unknown>> {
  status: number;
  body: T;
  replayed: boolean;
}

export async function runSecretIdempotent<T extends Record<string, unknown>>(
  env: Env,
  options: {
    scope: string;
    key: string;
    request: unknown;
    expiresInSeconds?: number;
    operation: () => Promise<{ status?: number; body: T }>;
    replay: () => Promise<{ status?: number; body: T }>;
  },
): Promise<StoredResponse<T>> {
  if (!/^[A-Za-z0-9._:-]{8,256}$/u.test(options.key)) {
    throw new ApiError("INVALID_IDEMPOTENCY_KEY", "幂等操作编号格式无效。", {
      status: 400,
    });
  }
  const requestDigest = await sha256Hex(stableJson(options.request));
  const now = new Date();
  const expiresAt = addSeconds(
    now,
    options.expiresInSeconds ?? 24 * 60 * 60,
  ).toISOString();
  const reservation = await env.DB.prepare(
    `INSERT OR IGNORE INTO idempotency_records (
       scope, idempotency_key, request_digest,
       response_status, response_body, expires_at
     ) VALUES (?, ?, ?, 102, '{"pending":true}', ?)`,
  )
    .bind(options.scope, options.key, requestDigest, expiresAt)
    .run();

  if (Number(reservation.meta.changes ?? 0) === 0) {
    const existing = await env.DB.prepare(
      `SELECT request_digest, response_status, expires_at
         FROM idempotency_records
        WHERE scope = ? AND idempotency_key = ?
        LIMIT 1`,
    )
      .bind(options.scope, options.key)
      .first<Record<string, unknown>>();
    if (existing === null) {
      throw new ApiError("IDEMPOTENCY_RETRY", "操作状态尚未确定，请重试。", {
        status: 409,
        retryable: true,
      });
    }
    if (String(existing.request_digest) !== requestDigest) {
      throw new ApiError(
        "IDEMPOTENCY_CONFLICT",
        "同一操作编号不能用于不同请求。",
        { status: 409 },
      );
    }
    if (String(existing.expires_at) <= now.toISOString()) {
      await env.DB.prepare(
        "DELETE FROM idempotency_records WHERE scope = ? AND idempotency_key = ?",
      )
        .bind(options.scope, options.key)
        .run();
      return runSecretIdempotent(env, options);
    }
    const status = Number(existing.response_status);
    if (status === 102) {
      throw new ApiError("IDEMPOTENCY_IN_PROGRESS", "该操作正在处理中。", {
        status: 409,
        retryable: true,
      });
    }
    const replayed = await options.replay();
    return {
      status: replayed.status ?? status,
      body: replayed.body,
      replayed: true,
    };
  }

  try {
    const result = await options.operation();
    const status = result.status ?? 200;
    await env.DB.prepare(
      `UPDATE idempotency_records
          SET response_status = ?, response_body = '{"complete":true}', expires_at = ?
        WHERE scope = ? AND idempotency_key = ?`,
    )
      .bind(status, expiresAt, options.scope, options.key)
      .run();
    return { status, body: result.body, replayed: false };
  } catch (error) {
    await env.DB.prepare(
      "DELETE FROM idempotency_records WHERE scope = ? AND idempotency_key = ?",
    )
      .bind(options.scope, options.key)
      .run();
    throw error;
  }
}

export async function runIdempotent<T extends Record<string, unknown>>(
  env: Env,
  options: {
    scope: string;
    key: string;
    request: unknown;
    expiresInSeconds?: number;
    operation: () => Promise<{ status?: number; body: T }>;
  },
): Promise<StoredResponse<T>> {
  if (!/^[A-Za-z0-9._:-]{8,256}$/u.test(options.key)) {
    throw new ApiError("INVALID_IDEMPOTENCY_KEY", "幂等操作编号格式无效。", {
      status: 400,
    });
  }
  const requestDigest = await sha256Hex(stableJson(options.request));
  const now = new Date();
  const expiresAt = addSeconds(
    now,
    options.expiresInSeconds ?? 24 * 60 * 60,
  ).toISOString();
  const pendingBody = stableJson({ pending: true });
  const reservation = await env.DB.prepare(
    `INSERT OR IGNORE INTO idempotency_records (
       scope, idempotency_key, request_digest,
       response_status, response_body, expires_at
     ) VALUES (?, ?, ?, 102, ?, ?)`,
  )
    .bind(options.scope, options.key, requestDigest, pendingBody, expiresAt)
    .run();

  if (Number(reservation.meta.changes ?? 0) === 0) {
    const existing = await env.DB.prepare(
      `SELECT request_digest, response_status, response_body, expires_at
         FROM idempotency_records
        WHERE scope = ? AND idempotency_key = ?
        LIMIT 1`,
    )
      .bind(options.scope, options.key)
      .first<Record<string, unknown>>();
    if (existing === null) {
      throw new ApiError("IDEMPOTENCY_RETRY", "操作状态尚未确定，请重试。", {
        status: 409,
        retryable: true,
      });
    }
    if (String(existing.request_digest) !== requestDigest) {
      throw new ApiError(
        "IDEMPOTENCY_CONFLICT",
        "同一操作编号不能用于不同请求。",
        { status: 409 },
      );
    }
    if (String(existing.expires_at) <= now.toISOString()) {
      await env.DB.prepare(
        "DELETE FROM idempotency_records WHERE scope = ? AND idempotency_key = ?",
      )
        .bind(options.scope, options.key)
        .run();
      return runIdempotent(env, options);
    }
    const status = Number(existing.response_status);
    if (status === 102) {
      throw new ApiError("IDEMPOTENCY_IN_PROGRESS", "该操作正在处理中。", {
        status: 409,
        retryable: true,
      });
    }
    let body: unknown;
    try {
      body = JSON.parse(String(existing.response_body));
    } catch (error) {
      throw new ApiError("IDEMPOTENCY_STATE_INVALID", "幂等响应状态损坏。", {
        status: 500,
        retryable: true,
        cause: error,
      });
    }
    if (typeof body !== "object" || body === null || Array.isArray(body)) {
      throw new ApiError("IDEMPOTENCY_STATE_INVALID", "幂等响应状态损坏。", {
        status: 500,
        retryable: true,
      });
    }
    return { status, body: body as T, replayed: true };
  }

  try {
    const result = await options.operation();
    const status = result.status ?? 200;
    await env.DB.prepare(
      `UPDATE idempotency_records
          SET response_status = ?, response_body = ?, expires_at = ?
        WHERE scope = ? AND idempotency_key = ?`,
    )
      .bind(
        status,
        stableJson(result.body),
        expiresAt,
        options.scope,
        options.key,
      )
      .run();
    return { status, body: result.body, replayed: false };
  } catch (error) {
    await env.DB.prepare(
      "DELETE FROM idempotency_records WHERE scope = ? AND idempotency_key = ?",
    )
      .bind(options.scope, options.key)
      .run();
    throw error;
  }
}
