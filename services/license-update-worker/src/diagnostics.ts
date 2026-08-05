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
    const now = new Date();
    const expiresAt = addSeconds(now, 15 * 60);
    const expiresEpoch = Math.floor(expiresAt.getTime() / 1000);
    const sessionId = randomId("diag_", 18);
    const objectKey = [
      "diagnostics",
      now.toISOString().slice(0, 10),
      authenticated.license.id,
      authenticated.device.id,
      `${sessionId}.zip`,
    ].join("/");
    await c.env.DB.prepare(
      `INSERT INTO diagnostic_submissions (
         id, license_id, device_id, object_key, size, sha256,
         client_version, launcher_version, status, expires_at, created_at
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'created', ?, ?)`,
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
        expiresAt.toISOString(),
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
      metadata: { size_bytes: declaredSize },
    });
    return c.json(
      {
        submission_id: sessionId,
        upload_url: `/v1/diagnostics/${sessionId}/content`,
        upload_token: uploadToken,
        expires_at: expiresAt.toISOString(),
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
              status, expires_at
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
    if (String(row.expires_at) <= now) {
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
      await c.env.DIAGNOSTICS.put(String(row.object_key), content, {
        httpMetadata: { contentType: "application/zip" },
        customMetadata: {
          submission_id: submissionId,
          license_id: String(row.license_id),
          device_id: String(row.device_id),
          sha256: digest,
        },
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
