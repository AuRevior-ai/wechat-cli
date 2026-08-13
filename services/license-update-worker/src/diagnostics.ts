import type { Hono } from "hono";

import { authenticateDevice } from "./auth";
import {
  constantTimeEqual,
  hmacSha256Hex,
  randomId,
  randomToken,
  sha256Hex,
} from "./crypto";
import { ApiError, readJsonObject, requiredInteger, requiredString } from "./http";
import { addSeconds, enforceRateLimit, isoNow, writeAudit } from "./service";
import type { Env } from "./types";

interface WorkerVariables {
  requestId: string;
}

type WorkerApp = Hono<{ Bindings: Env; Variables: WorkerVariables }>;

export const DIAGNOSTIC_CONSENT_VERSION = "diagnostics-consent-v1";

export function diagnosticDeadlines(now: Date): {
  upload_expires_at: string;
  retention_expires_at: string;
} {
  if (!(now instanceof Date) || !Number.isFinite(now.getTime())) {
    throw new TypeError("diagnostic clock is invalid");
  }
  return {
    upload_expires_at: addSeconds(now, 15 * 60).toISOString(),
    retention_expires_at: addSeconds(now, 7 * 24 * 60 * 60).toISOString(),
  };
}

export function diagnosticObjectKey(now: Date, submissionId: string): string {
  if (!(now instanceof Date) || !Number.isFinite(now.getTime())) {
    throw new TypeError("diagnostic clock is invalid");
  }
  if (!/^diag_[A-Za-z0-9_-]{12,128}$/u.test(submissionId)) {
    throw new TypeError("diagnostic submission id is invalid");
  }
  return `diagnostics/${now.toISOString().slice(0, 10)}/${submissionId}.zip`;
}

export function validateDiagnosticConsent(value: unknown): string {
  if (value !== DIAGNOSTIC_CONSENT_VERSION) {
    throw new ApiError("DIAGNOSTIC_CONSENT_REQUIRED", "诊断提交需要当前版本的明确同意。", {
      status: 400,
      retryable: false,
    });
  }
  return DIAGNOSTIC_CONSENT_VERSION;
}

export async function putDiagnosticObject(
  env: Env,
  options: {
    objectKey: string;
    content: ArrayBuffer;
    submissionId: string;
    sha256: string;
  },
): Promise<void> {
  await env.DIAGNOSTICS.put(options.objectKey, options.content, {
    httpMetadata: { contentType: "application/zip" },
    customMetadata: {
      submission_id: options.submissionId,
      sha256: options.sha256,
    },
  });
}

export async function cleanupExpiredDiagnostics(
  env: Env,
  now: Date = new Date(),
): Promise<void> {
  const nowIso = now.toISOString();
  const expired = await env.DB.prepare(
    `SELECT id, object_key, status
       FROM diagnostic_submissions
      WHERE retention_expires_at <= ? AND status != 'deleted'
      LIMIT 500`,
  )
    .bind(nowIso)
    .all<Record<string, unknown>>();
  for (const row of expired.results) {
    if (row.status === "complete") {
      await env.DIAGNOSTICS.delete(String(row.object_key));
    }
    await env.DB.prepare(
      "UPDATE diagnostic_submissions SET status = 'deleted' WHERE id = ?",
    )
      .bind(String(row.id))
      .run();
  }
}

function maximumDiagnosticBytes(env: Env): number {
  const value = Number.parseInt(env.MAX_DIAGNOSTIC_BYTES, 10);
  if (!Number.isFinite(value) || value < 1024 || value > 100 * 1024 * 1024) {
    throw new ApiError("SERVICE_CONFIGURATION_INVALID", "诊断包大小配置无效。", {
      status: 500,
      retryable: true,
    });
  }
  return value;
}

async function createUploadToken(
  env: Env,
  sessionId: string,
  expiresAtEpoch: number,
): Promise<string> {
  const nonce = randomToken(18);
  const message = `${sessionId}\u0000${expiresAtEpoch}\u0000${nonce}`;
  const signature = await hmacSha256Hex(env.DOWNLOAD_TICKET_SECRET, message);
  return `diag_${expiresAtEpoch}.${nonce}.${signature}`;
}

async function verifyUploadToken(
  env: Env,
  sessionId: string,
  token: string,
): Promise<void> {
  const match = /^diag_(\d{10})\.([A-Za-z0-9_-]{16,128})\.([0-9a-f]{64})$/u.exec(
    token,
  );
  if (
    match === null ||
    match[1] === undefined ||
    match[2] === undefined ||
    match[3] === undefined
  ) {
    throw new ApiError("DIAGNOSTIC_UPLOAD_NOT_AUTHORIZED", "诊断上传令牌无效。", {
      status: 401,
    });
  }
  const expiresAtEpoch = Number.parseInt(match[1], 10);
  if (expiresAtEpoch <= Math.floor(Date.now() / 1000)) {
    throw new ApiError("DIAGNOSTIC_UPLOAD_TOKEN_EXPIRED", "诊断上传令牌已过期。", {
      status: 401,
    });
  }
  const expected = await hmacSha256Hex(
    env.DOWNLOAD_TICKET_SECRET,
    `${sessionId}\u0000${expiresAtEpoch}\u0000${match[2]}`,
  );
  if (!constantTimeEqual(expected, match[3])) {
    throw new ApiError("DIAGNOSTIC_UPLOAD_NOT_AUTHORIZED", "诊断上传令牌无效。", {
      status: 401,
    });
  }
}

function diagnosticAuthorization(request: Request): string {
  const header = request.headers.get("Authorization");
  const match = header === null ? null : /^Diagnostic\s+(.+)$/iu.exec(header.trim());
  if (match === null || match[1] === undefined) {
    throw new ApiError("DIAGNOSTIC_UPLOAD_NOT_AUTHORIZED", "缺少诊断上传令牌。", {
      status: 401,
    });
  }
  return match[1];
}

export function registerDiagnosticRoutes(app: WorkerApp): void {
  app.post("/v1/diagnostics/sessions", async (c) => {
    const authenticated = await authenticateDevice(c);
    await enforceRateLimit(c, {
      name: "diagnostic-session",
      maximum: 5,
      windowSeconds: 60 * 60,
      identity: authenticated.device.id,
    });
    const request = await readJsonObject(c.req.raw);
    const clientVersion = requiredString(request, "client_version", { maximum: 64 });
    const launcherVersion = requiredString(request, "launcher_version", {
      maximum: 64,
    });
    const declaredSize = requiredInteger(request, "size_bytes", {
      minimum: 1,
      maximum: maximumDiagnosticBytes(c.env),
    });
    const declaredSha256 = requiredString(request, "sha256", {
      minimum: 64,
      maximum: 64,
      pattern: /^[0-9a-f]{64}$/iu,
    }).toLowerCase();
    const consentVersion = validateDiagnosticConsent(request.consent_version);
    const now = new Date();
    const deadlines = diagnosticDeadlines(now);
    const expiresEpoch = Math.floor(Date.parse(deadlines.upload_expires_at) / 1000);
    const sessionId = randomId("diag_", 18);
    const objectKey = diagnosticObjectKey(now, sessionId);
    await c.env.DB.prepare(
      `INSERT INTO diagnostic_submissions (
         id, license_id, device_id, object_key, size, sha256,
         client_version, launcher_version, status, expires_at,
         upload_expires_at, retention_expires_at, consent_version, created_at
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'created', ?, ?, ?, ?, ?)`,
    )
      .bind(
        sessionId,
        authenticated.license.id,
        authenticated.device.id,
        objectKey,
        declaredSize,
        declaredSha256,
        clientVersion,
        launcherVersion,
        deadlines.retention_expires_at,
        deadlines.upload_expires_at,
        deadlines.retention_expires_at,
        consentVersion,
        now.toISOString(),
      )
      .run();
    const uploadToken = await createUploadToken(c.env, sessionId, expiresEpoch);
    await writeAudit(c.env, {
      actorType: "device",
      actorId: authenticated.device.id,
      action: "diagnostic.session.create",
      targetType: "diagnostic",
      targetId: sessionId,
      result: "success",
      requestId: c.get("requestId"),
      metadata: {
        size_bytes: declaredSize,
        consent_version: consentVersion,
        retention_days: 7,
      },
    });
    return c.json(
      {
        submission_id: sessionId,
        upload_url: `/v1/diagnostics/${sessionId}/content`,
        upload_token: uploadToken,
        expires_at: deadlines.upload_expires_at,
        upload_expires_at: deadlines.upload_expires_at,
        retention_expires_at: deadlines.retention_expires_at,
        retention_days: 7,
        consent_version: consentVersion,
        maximum_bytes: maximumDiagnosticBytes(c.env),
      },
      201,
    );
  });

  app.put("/v1/diagnostics/:submissionId/content", async (c) => {
    const submissionId = requiredString(
      { submission_id: c.req.param("submissionId") },
      "submission_id",
      {
        minimum: 16,
        maximum: 128,
        pattern: /^diag_[A-Za-z0-9_-]+$/u,
      },
    );
    await verifyUploadToken(
      c.env,
      submissionId,
      diagnosticAuthorization(c.req.raw),
    );
    const row = await c.env.DB.prepare(
      `SELECT id, license_id, device_id, object_key, size, sha256,
              status, upload_expires_at, retention_expires_at
         FROM diagnostic_submissions
        WHERE id = ?
        LIMIT 1`,
    )
      .bind(submissionId)
      .first<Record<string, unknown>>();
    if (row === null) {
      throw new ApiError("DIAGNOSTIC_NOT_FOUND", "诊断提交不存在。", {
        status: 404,
      });
    }
    const now = isoNow();
    if (String(row.upload_expires_at) <= now) {
      throw new ApiError("DIAGNOSTIC_SESSION_EXPIRED", "诊断提交会话已过期。", {
        status: 410,
      });
    }
    if (row.status === "complete") {
      return c.json({
        ok: true,
        submission_id: submissionId,
        status: "complete",
        replayed: true,
      });
    }
    if (row.status !== "created" && row.status !== "uploading") {
      throw new ApiError("DIAGNOSTIC_STATE_INVALID", "诊断提交状态不可上传。", {
        status: 409,
      });
    }
    const maximum = maximumDiagnosticBytes(c.env);
    const lengthHeader = c.req.header("Content-Length");
    if (lengthHeader !== undefined) {
      const length = Number.parseInt(lengthHeader, 10);
      if (!Number.isFinite(length) || length < 1 || length > maximum) {
        throw new ApiError("DIAGNOSTIC_TOO_LARGE", "诊断包大小无效。", {
          status: 413,
        });
      }
    }
    const contentType = c.req.header("Content-Type") ?? "";
    if (!/^(application\/zip|application\/octet-stream)(?:;|$)/iu.test(contentType)) {
      throw new ApiError("DIAGNOSTIC_CONTENT_TYPE_INVALID", "诊断包必须是 ZIP 文件。", {
        status: 415,
      });
    }
    await c.env.DB.prepare(
      "UPDATE diagnostic_submissions SET status = 'uploading' WHERE id = ?",
    )
      .bind(submissionId)
      .run();
    let content: ArrayBuffer;
    try {
      content = await c.req.arrayBuffer();
      if (content.byteLength < 1 || content.byteLength > maximum) {
        throw new ApiError("DIAGNOSTIC_TOO_LARGE", "诊断包大小无效。", {
          status: 413,
        });
      }
      if (Number(row.size) !== content.byteLength) {
        throw new ApiError("DIAGNOSTIC_SIZE_MISMATCH", "诊断包大小与声明不一致。", {
          status: 409,
        });
      }
      const digest = await sha256Hex(content);
      if (!constantTimeEqual(digest, String(row.sha256))) {
        throw new ApiError("DIAGNOSTIC_HASH_MISMATCH", "诊断包摘要与声明不一致。", {
          status: 409,
        });
      }
      await putDiagnosticObject(c.env, {
        objectKey: String(row.object_key),
        content,
        submissionId,
        sha256: digest,
      });
      const submittedAt = isoNow();
      await c.env.DB.prepare(
        `UPDATE diagnostic_submissions
            SET status = 'complete', submitted_at = ?, size = ?, sha256 = ?
          WHERE id = ?`,
      )
        .bind(submittedAt, content.byteLength, digest, submissionId)
        .run();
      await writeAudit(c.env, {
        actorType: "device",
        actorId: String(row.device_id),
        action: "diagnostic.upload",
        targetType: "diagnostic",
        targetId: submissionId,
        result: "success",
        requestId: c.get("requestId"),
        metadata: { size_bytes: content.byteLength },
      });
      return c.json({
        ok: true,
        submission_id: submissionId,
        status: "complete",
        size_bytes: content.byteLength,
        sha256: digest,
      });
    } catch (error) {
      await c.env.DB.prepare(
        "UPDATE diagnostic_submissions SET status = 'failed' WHERE id = ?",
      )
        .bind(submissionId)
        .run();
      throw error;
    }
  });
}
