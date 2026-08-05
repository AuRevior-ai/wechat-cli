import type { Hono } from "hono";

import { authenticateAdmin } from "./auth";
import {
  base64ToBytes,
  decryptContacts,
  deriveLicenseKey,
  deriveOpaqueId,
  encryptContacts,
  hmacSha256Hex,
  licenseKeyHint,
  normalizeLicenseKey,
  randomId,
  sha256Hex,
} from "./crypto";
import {
  ApiError,
  optionalString,
  readJsonObject,
  requiredInteger,
  requiredString,
} from "./http";
import { parseSemanticVersion } from "./semver";
import {
  enforceRateLimit,
  isoNow,
  runIdempotent,
  runSecretIdempotent,
  writeAudit,
} from "./service";
import type { LicenseContacts } from "./crypto";
import type { Env } from "./types";

interface WorkerVariables {
  requestId: string;
}

type WorkerApp = Hono<{ Bindings: Env; Variables: WorkerVariables }>;

function parseBoolean(value: unknown, name: string): boolean | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "boolean") {
    throw new ApiError("INVALID_REQUEST", `${name} 必须是布尔值。`, { status: 400 });
  }
  return value;
}

function databaseBytes(value: unknown, name: string): Uint8Array<ArrayBuffer> {
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
  throw new ApiError(
    "CONTACT_ENCRYPTION_STATE_INVALID",
    `联系人加密字段 ${name} 不是二进制数据。`,
    { status: 500, retryable: false },
  );
}

function contactFields(request: Record<string, unknown>): LicenseContacts {
  const contactsValue = request.contacts;
  if (contactsValue === undefined || contactsValue === null) {
    return {};
  }
  if (
    typeof contactsValue !== "object" ||
    Array.isArray(contactsValue)
  ) {
    throw new ApiError("INVALID_REQUEST", "contacts 必须是对象。", { status: 400 });
  }
  const contacts = contactsValue as Record<string, unknown>;
  const result: LicenseContacts = {};
  const email = optionalString(contacts, "email", 320);
  const wechat = optionalString(contacts, "wechat", 320);
  const other = optionalString(contacts, "other", 2048);
  const notes = optionalString(contacts, "notes", 2048);
  if (email !== undefined) result.email = email;
  if (wechat !== undefined) result.wechat = wechat;
  if (other !== undefined) result.other = other;
  if (notes !== undefined) result.notes = notes;
  return result;
}

function contactKey(env: Env, version: number): string {
  if (!Number.isInteger(version) || version < 1 || version > 9999) {
    throw new ApiError("SERVICE_CONFIGURATION_INVALID", "联系人密钥版本无效。", {
      status: 500,
      retryable: true,
    });
  }
  const keyName = `CONTACT_ENCRYPTION_KEY_V${version}`;
  const key = (env as unknown as Record<string, unknown>)[keyName];
  if (typeof key !== "string" || key.length === 0) {
    throw new ApiError(
      "CONTACT_ENCRYPTION_KEY_MISSING",
      `联系人加密密钥版本 ${version} 缺失。`,
      { status: 500, retryable: false },
    );
  }
  return key;
}

function currentContactKey(env: Env): { version: number; key: string } {
  const version = Number.parseInt(env.CONTACT_ENCRYPTION_KEY_VERSION, 10);
  return { version, key: contactKey(env, version) };
}

interface GeneratedLicense {
  licenseId: string;
  licenseKey: string;
  keyHint: string;
  keyDigest: string;
  generationIndex: number;
}

async function deriveGeneratedLicense(
  env: Env,
  adminId: string,
  generationRequestId: string,
  generationIndex: number,
): Promise<GeneratedLicense> {
  if (!Number.isInteger(generationIndex) || generationIndex < 0) {
    throw new Error("generationIndex must be a non-negative integer");
  }
  const context = `${adminId}\u0000${generationRequestId}\u0000${generationIndex}`;
  const licenseKey = await deriveLicenseKey(env.LICENSE_KEY_PEPPER, context);
  const licenseId = await deriveOpaqueId(
    "lic_",
    env.LICENSE_KEY_PEPPER,
    context,
  );
  const normalized = normalizeLicenseKey(licenseKey);
  return {
    licenseId,
    licenseKey,
    keyHint: licenseKeyHint(licenseKey),
    keyDigest: await hmacSha256Hex(
      env.LICENSE_KEY_PEPPER,
      `license-key\u0000${normalized}`,
    ),
    generationIndex,
  };
}

function licenseInsertStatement(
  env: Env,
  adminId: string,
  generationRequestId: string,
  generated: GeneratedLicense,
  options: {
    maximumDevices: number;
    channel: "stable" | "beta";
    now: string;
  },
): D1PreparedStatement {
  return env.DB.prepare(
    `INSERT INTO licenses (
       id, key_digest, key_hint, status, max_devices,
       release_channel, revision, created_at, updated_at,
       created_by_admin_id, generation_request_id, generation_index
     ) VALUES (?, ?, ?, 'active', ?, ?, 1, ?, ?, ?, ?, ?)`,
  ).bind(
    generated.licenseId,
    generated.keyDigest,
    generated.keyHint,
    options.maximumDevices,
    options.channel,
    options.now,
    options.now,
    adminId,
    generationRequestId,
    generated.generationIndex,
  );
}

async function createSingleLicenseRecord(
  env: Env,
  adminId: string,
  generationRequestId: string,
  options: {
    maximumDevices: number;
    channel: "stable" | "beta";
    contacts: LicenseContacts;
    now: string;
  },
): Promise<GeneratedLicense> {
  const generated = await deriveGeneratedLicense(
    env,
    adminId,
    generationRequestId,
    0,
  );
  const statements: D1PreparedStatement[] = [
    licenseInsertStatement(
      env,
      adminId,
      generationRequestId,
      generated,
      options,
    ),
  ];
  if (Object.keys(options.contacts).length > 0) {
    const encryption = currentContactKey(env);
    const encrypted = await encryptContacts(options.contacts, {
      licenseId: generated.licenseId,
      keyVersion: encryption.version,
      encryptionKeyBase64: encryption.key,
      lookupPepper: env.CONTACT_LOOKUP_PEPPER,
    });
    statements.push(
      env.DB.prepare(
        `INSERT INTO license_contacts (
           license_id, ciphertext, iv, encryption_key_version,
           email_lookup_digest, wechat_lookup_digest,
           other_lookup_digest, updated_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      ).bind(
        generated.licenseId,
        encrypted.ciphertext,
        encrypted.iv,
        encrypted.keyVersion,
        encrypted.emailLookupDigest,
        encrypted.wechatLookupDigest,
        encrypted.otherLookupDigest,
        options.now,
      ),
    );
  }
  await env.DB.batch(statements);
  return generated;
}

async function createBatchLicenseRecords(
  env: Env,
  adminId: string,
  generationRequestId: string,
  options: {
    count: number;
    maximumDevices: number;
    channel: "stable" | "beta";
    now: string;
  },
): Promise<GeneratedLicense[]> {
  const generated = await Promise.all(
    Array.from({ length: options.count }, (_value, index) =>
      deriveGeneratedLicense(env, adminId, generationRequestId, index),
    ),
  );
  await env.DB.batch(
    generated.map((item) =>
      licenseInsertStatement(
        env,
        adminId,
        generationRequestId,
        item,
        options,
      ),
    ),
  );
  return generated;
}

async function replayGeneratedLicenses(
  env: Env,
  adminId: string,
  generationRequestId: string,
  expectedCount: number,
): Promise<
  Array<
    GeneratedLicense & {
      maximumDevices: number;
      channel: string;
      createdAt: string;
    }
  >
> {
  const rows = await env.DB.prepare(
    `SELECT generation_index, max_devices, release_channel, created_at
       FROM licenses
      WHERE created_by_admin_id = ? AND generation_request_id = ?
      ORDER BY generation_index ASC`,
  )
    .bind(adminId, generationRequestId)
    .all<Record<string, unknown>>();
  if (rows.results.length !== expectedCount) {
    throw new ApiError(
      "IDEMPOTENCY_STATE_INVALID",
      "许可证生成记录不完整，无法安全重放。",
      { status: 500, retryable: true },
    );
  }
  return Promise.all(
    rows.results.map(async (row, expectedIndex) => {
      const generationIndex = Number(row.generation_index);
      if (generationIndex !== expectedIndex) {
        throw new ApiError(
          "IDEMPOTENCY_STATE_INVALID",
          "许可证生成记录顺序无效。",
          { status: 500, retryable: true },
        );
      }
      const generated = await deriveGeneratedLicense(
        env,
        adminId,
        generationRequestId,
        generationIndex,
      );
      return {
        ...generated,
        maximumDevices: Number(row.max_devices),
        channel: String(row.release_channel),
        createdAt: String(row.created_at),
      };
    }),
  );
}

function generatedLicenseBody(
  generated: GeneratedLicense,
  options: {
    maximumDevices: number;
    channel: string;
    createdAt: string;
  },
): Record<string, unknown> {
  return {
    license_id: generated.licenseId,
    license_key: generated.licenseKey,
    license_hint: generated.keyHint,
    status: "active",
    maximum_devices: options.maximumDevices,
    release_channel: options.channel,
    created_at: options.createdAt,
  };
}

function licenseSummary(row: Record<string, unknown>): Record<string, unknown> {
  return {
    license_id: String(row.id),
    license_hint: String(row.key_hint),
    status: String(row.status),
    maximum_devices: Number(row.max_devices),
    active_devices: Number(row.active_devices ?? 0),
    release_channel: String(row.release_channel),
    revision: Number(row.revision),
    created_at: String(row.created_at),
    updated_at: String(row.updated_at),
  };
}

export function registerAdminRoutes(app: WorkerApp): void {
  app.post("/v1/admin/licenses", async (c) => {
    const admin = await authenticateAdmin(c, "licenses:write");
    await enforceRateLimit(c, {
      name: "admin-license-create",
      maximum: 120,
      windowSeconds: 60,
      identity: admin.id,
    });
    const request = await readJsonObject(c.req.raw);
    const maximumDevices =
      request.maximum_devices === undefined
        ? 3
        : requiredInteger(request, "maximum_devices", { minimum: 1, maximum: 100 });
    const channel = (optionalString(request, "release_channel", 16) ??
      "stable") as "stable" | "beta";
    if (channel !== "stable" && channel !== "beta") {
      throw new ApiError("INVALID_REQUEST", "release_channel 无效。", { status: 400 });
    }
    const nonce = requiredString(request, "operation_nonce", {
      minimum: 8,
      maximum: 256,
    });
    const contacts = contactFields(request);
    const response = await runSecretIdempotent(c.env, {
      scope: `admin-license-create:${admin.id}`,
      key: nonce,
      request: { maximumDevices, channel, contacts },
      operation: async () => {
        const now = isoNow();
        const created = await createSingleLicenseRecord(
          c.env,
          admin.id,
          nonce,
          {
            maximumDevices,
            channel,
            contacts,
            now,
          },
        );
        await writeAudit(c.env, {
          actorType: "admin",
          actorId: admin.id,
          action: "license.create",
          targetType: "license",
          targetId: created.licenseId,
          result: "success",
          requestId: c.get("requestId"),
          metadata: {
            maximum_devices: maximumDevices,
            release_channel: channel,
            contact_fields: Object.keys(contacts),
          },
        });
        return {
          status: 201,
          body: generatedLicenseBody(created, {
            maximumDevices,
            channel,
            createdAt: now,
          }),
        };
      },
      replay: async () => {
        const [created] = await replayGeneratedLicenses(
          c.env,
          admin.id,
          nonce,
          1,
        );
        if (created === undefined) {
          throw new ApiError(
            "IDEMPOTENCY_STATE_INVALID",
            "许可证生成记录缺失。",
            { status: 500, retryable: true },
          );
        }
        return {
          status: 201,
          body: generatedLicenseBody(created, {
            maximumDevices: created.maximumDevices,
            channel: created.channel,
            createdAt: created.createdAt,
          }),
        };
      },
    });
    return c.json(response.body, response.status as 201);
  });

  app.post("/v1/admin/licenses/batch", async (c) => {
    const admin = await authenticateAdmin(c, "licenses:write");
    const request = await readJsonObject(c.req.raw);
    const count = requiredInteger(request, "count", { minimum: 1, maximum: 100 });
    const maximumDevices =
      request.maximum_devices === undefined
        ? 3
        : requiredInteger(request, "maximum_devices", { minimum: 1, maximum: 100 });
    const channel = optionalString(request, "release_channel", 16) ?? "stable";
    if (channel !== "stable" && channel !== "beta") {
      throw new ApiError("INVALID_REQUEST", "release_channel 无效。", { status: 400 });
    }
    const nonce = requiredString(request, "operation_nonce", {
      minimum: 8,
      maximum: 256,
    });
    const response = await runSecretIdempotent(c.env, {
      scope: `admin-license-batch:${admin.id}`,
      key: nonce,
      request: { count, maximumDevices, channel },
      operation: async () => {
        const now = isoNow();
        const generated = await createBatchLicenseRecords(
          c.env,
          admin.id,
          nonce,
          {
            count,
            maximumDevices,
            channel,
            now,
          },
        );
        const created = generated.map((item) =>
          generatedLicenseBody(item, {
            maximumDevices,
            channel,
            createdAt: now,
          }),
        );
        await writeAudit(c.env, {
          actorType: "admin",
          actorId: admin.id,
          action: "license.batch_create",
          result: "success",
          requestId: c.get("requestId"),
          metadata: {
            count,
            maximum_devices: maximumDevices,
            release_channel: channel,
          },
        });
        return { status: 201, body: { licenses: created } };
      },
      replay: async () => {
        const generated = await replayGeneratedLicenses(
          c.env,
          admin.id,
          nonce,
          count,
        );
        return {
          status: 201,
          body: {
            licenses: generated.map((item) =>
              generatedLicenseBody(item, {
                maximumDevices: item.maximumDevices,
                channel: item.channel,
                createdAt: item.createdAt,
              }),
            ),
          },
        };
      },
    });
    return c.json(response.body, response.status as 201);
  });

  app.get("/v1/admin/licenses", async (c) => {
    await authenticateAdmin(c, "licenses:read");
    const status = c.req.query("status")?.trim();
    const query = c.req.query("query")?.trim();
    const limit = Math.min(200, Math.max(1, Number.parseInt(c.req.query("limit") ?? "50", 10) || 50));
    const clauses: string[] = [];
    const bindings: unknown[] = [];
    if (status !== undefined && status.length > 0) {
      if (!["active", "suspended", "revoked"].includes(status)) {
        throw new ApiError("INVALID_REQUEST", "status 查询值无效。", { status: 400 });
      }
      clauses.push("l.status = ?");
      bindings.push(status);
    }
    if (query !== undefined && query.length > 0) {
      const normalizedQuery = query.normalize("NFKC").trim().toLowerCase();
      const lookupDigest = await hmacSha256Hex(
        c.env.CONTACT_LOOKUP_PEPPER,
        normalizedQuery,
      );
      const hint = query.replace(/[^A-Za-z0-9]/gu, "").slice(-4).toUpperCase();
      clauses.push(
        `(l.id = ? OR l.key_hint = ? OR lc.email_lookup_digest = ? OR
          lc.wechat_lookup_digest = ? OR lc.other_lookup_digest = ?)`,
      );
      bindings.push(query, hint, lookupDigest, lookupDigest, lookupDigest);
    }
    const where = clauses.length > 0 ? `WHERE ${clauses.join(" AND ")}` : "";
    const rows = await c.env.DB.prepare(
      `SELECT l.id, l.key_hint, l.status, l.max_devices,
              l.release_channel, l.revision, l.created_at, l.updated_at,
              SUM(CASE WHEN d.status = 'active' THEN 1 ELSE 0 END) AS active_devices
         FROM licenses l
         LEFT JOIN license_contacts lc ON lc.license_id = l.id
         LEFT JOIN devices d ON d.license_id = l.id
         ${where}
        GROUP BY l.id
        ORDER BY l.created_at DESC
        LIMIT ?`,
    )
      .bind(...bindings, limit)
      .all<Record<string, unknown>>();
    return c.json({ licenses: rows.results.map(licenseSummary) });
  });

  app.patch("/v1/admin/licenses/:licenseId/status", async (c) => {
    const admin = await authenticateAdmin(c, "licenses:write");
    const licenseId = requiredString(
      { license_id: c.req.param("licenseId") },
      "license_id",
      { maximum: 128 },
    );
    const request = await readJsonObject(c.req.raw);
    const status = requiredString(request, "status", { maximum: 16 });
    if (!["active", "suspended", "revoked"].includes(status)) {
      throw new ApiError("INVALID_REQUEST", "许可证状态无效。", { status: 400 });
    }
    const nonce = requiredString(request, "operation_nonce", {
      minimum: 8,
      maximum: 256,
    });
    const response = await runIdempotent(c.env, {
      scope: `admin-license-status:${admin.id}`,
      key: nonce,
      request: { licenseId, status },
      operation: async () => {
        const now = isoNow();
        const updated = await c.env.DB.prepare(
          `UPDATE licenses
              SET status = ?, revision = revision + 1, updated_at = ?,
                  suspended_at = CASE WHEN ? = 'suspended' THEN ? ELSE NULL END,
                  revoked_at = CASE WHEN ? = 'revoked' THEN ? ELSE revoked_at END
            WHERE id = ?`,
        )
          .bind(status, now, status, now, status, now, licenseId)
          .run();
        if (Number(updated.meta.changes ?? 0) !== 1) {
          throw new ApiError("LICENSE_NOT_FOUND", "许可证不存在。", { status: 404 });
        }
        await writeAudit(c.env, {
          actorType: "admin",
          actorId: admin.id,
          action: `license.${status}`,
          targetType: "license",
          targetId: licenseId,
          result: "success",
          requestId: c.get("requestId"),
        });
        return { body: { ok: true, license_id: licenseId, status, updated_at: now } };
      },
    });
    return c.json(response.body, response.status as 200);
  });

  app.get("/v1/admin/licenses/:licenseId/devices", async (c) => {
    await authenticateAdmin(c, "devices:read");
    const licenseId = c.req.param("licenseId");
    const rows = await c.env.DB.prepare(
      `SELECT id, display_name, status, first_activated_at,
              last_validated_at, last_app_version, last_launcher_version,
              disabled_at, unbound_at
         FROM devices WHERE license_id = ?
        ORDER BY first_activated_at ASC`,
    )
      .bind(licenseId)
      .all<Record<string, unknown>>();
    return c.json({
      devices: rows.results.map((row) => ({
        device_id: String(row.id),
        display_name: String(row.display_name),
        status: String(row.status),
        first_activated_at: String(row.first_activated_at),
        last_validated_at: row.last_validated_at,
        last_app_version: row.last_app_version,
        last_launcher_version: row.last_launcher_version,
        disabled_at: row.disabled_at,
        unbound_at: row.unbound_at,
      })),
    });
  });

  app.patch("/v1/admin/devices/:deviceId/status", async (c) => {
    const admin = await authenticateAdmin(c, "devices:write");
    const deviceId = c.req.param("deviceId");
    const request = await readJsonObject(c.req.raw);
    const status = requiredString(request, "status", { maximum: 16 });
    if (status !== "active" && status !== "disabled") {
      throw new ApiError("INVALID_REQUEST", "设备状态必须是 active 或 disabled。", {
        status: 400,
      });
    }
    const nonce = requiredString(request, "operation_nonce", { minimum: 8, maximum: 256 });
    const response = await runIdempotent(c.env, {
      scope: `admin-device-status:${admin.id}`,
      key: nonce,
      request: { deviceId, status },
      operation: async () => {
        const now = isoNow();
        const updated = await c.env.DB.prepare(
          `UPDATE devices
              SET status = ?, device_revision = device_revision + 1,
                  disabled_at = CASE WHEN ? = 'disabled' THEN ? ELSE NULL END
            WHERE id = ? AND status != 'unbound'`,
        )
          .bind(status, status, now, deviceId)
          .run();
        if (Number(updated.meta.changes ?? 0) !== 1) {
          throw new ApiError("DEVICE_NOT_FOUND", "设备不存在或已解绑。", { status: 404 });
        }
        await writeAudit(c.env, {
          actorType: "admin",
          actorId: admin.id,
          action: `device.${status}`,
          targetType: "device",
          targetId: deviceId,
          result: "success",
          requestId: c.get("requestId"),
        });
        return { body: { ok: true, device_id: deviceId, status } };
      },
    });
    return c.json(response.body, response.status as 200);
  });

  app.post("/v1/admin/devices/:deviceId/unbind", async (c) => {
    const admin = await authenticateAdmin(c, "devices:write");
    const deviceId = c.req.param("deviceId");
    const request = await readJsonObject(c.req.raw);
    const nonce = requiredString(request, "operation_nonce", { minimum: 8, maximum: 256 });
    const response = await runIdempotent(c.env, {
      scope: `admin-device-unbind:${admin.id}`,
      key: nonce,
      request: { deviceId },
      operation: async () => {
        const now = isoNow();
        const updated = await c.env.DB.prepare(
          `UPDATE devices
              SET status = 'unbound', unbound_at = ?,
                  token_version = token_version + 1,
                  device_revision = device_revision + 1
            WHERE id = ? AND status != 'unbound'`,
        )
          .bind(now, deviceId)
          .run();
        if (Number(updated.meta.changes ?? 0) !== 1) {
          throw new ApiError("DEVICE_NOT_FOUND", "设备不存在或已解绑。", { status: 404 });
        }
        await writeAudit(c.env, {
          actorType: "admin",
          actorId: admin.id,
          action: "device.unbind",
          targetType: "device",
          targetId: deviceId,
          result: "success",
          requestId: c.get("requestId"),
        });
        return { body: { ok: true, unbound_device_id: deviceId } };
      },
    });
    return c.json(response.body, response.status as 200);
  });

  app.post("/v1/admin/releases", async (c) => {
    const admin = await authenticateAdmin(c, "releases:write");
    const request = await readJsonObject(c.req.raw, { maximumBytes: 2 * 1024 * 1024 });
    const releaseId = requiredString(request, "release_id", { maximum: 128 });
    const version = requiredString(request, "version", { maximum: 64 });
    try {
      parseSemanticVersion(version);
    } catch (error) {
      throw new ApiError("INVALID_REQUEST", "发布版本无效。", { status: 400, cause: error });
    }
    const channel = requiredString(request, "channel", { maximum: 16 });
    if (channel !== "stable" && channel !== "beta") {
      throw new ApiError("INVALID_REQUEST", "发布通道无效。", { status: 400 });
    }
    const manifestContent = base64ToBytes(
      requiredString(request, "manifest_content_base64", { maximum: 1_500_000 }),
    );
    const manifestSignature = base64ToBytes(
      requiredString(request, "manifest_signature_base64", { maximum: 4096 }),
      64,
    );
    const manifestSha256 = requiredString(request, "manifest_sha256", {
      minimum: 64,
      maximum: 64,
      pattern: /^[0-9a-f]{64}$/iu,
    }).toLowerCase();
    if ((await sha256Hex(manifestContent)) !== manifestSha256) {
      throw new ApiError("UPDATE_HASH_MISMATCH", "清单摘要与原始字节不一致。", {
        status: 409,
      });
    }
    const packageSha256 = requiredString(request, "package_sha256", {
      minimum: 64,
      maximum: 64,
      pattern: /^[0-9a-f]{64}$/iu,
    }).toLowerCase();
    const packageSize = requiredInteger(request, "package_size", {
      minimum: 1,
      maximum: 8 * 1024 * 1024 * 1024,
    });
    const repository = requiredString(request, "github_repository", {
      maximum: 256,
      pattern: /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/u,
    });
    const githubReleaseId = requiredString(request, "github_release_id", {
      maximum: 64,
      pattern: /^\d+$/u,
    });
    const githubAssetId = requiredString(request, "github_asset_id", {
      maximum: 64,
      pattern: /^\d+$/u,
    });
    const assetName = requiredString(request, "github_asset_name", { maximum: 256 });
    const rolloutPercentage =
      request.rollout_percentage === undefined
        ? 100
        : requiredInteger(request, "rollout_percentage", { minimum: 0, maximum: 100 });
    const rolloutSeed = optionalString(request, "rollout_seed", 256) ?? randomId("rollout_", 18);
    const nonce = requiredString(request, "operation_nonce", { minimum: 8, maximum: 256 });
    const response = await runIdempotent(c.env, {
      scope: `admin-release-create:${admin.id}`,
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
        rolloutPercentage,
      },
      operation: async () => {
        const now = isoNow();
        await c.env.DB.prepare(
          `INSERT INTO releases (
             id, version, channel, manifest_content, manifest_signature,
             manifest_sha256, package_sha256, package_size,
             github_repository, github_release_id, github_asset_id,
             github_asset_name, rollout_percentage, rollout_seed,
             paused, enabled, published_at, created_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)`,
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
            rolloutPercentage,
            rolloutSeed,
            now,
            now,
          )
          .run();
        await writeAudit(c.env, {
          actorType: "admin",
          actorId: admin.id,
          action: "release.register",
          targetType: "release",
          targetId: releaseId,
          result: "success",
          requestId: c.get("requestId"),
          metadata: { version, channel, enabled: false, paused: true },
        });
        return {
          status: 201,
          body: {
            release_id: releaseId,
            version,
            channel,
            enabled: false,
            paused: true,
            rollout_percentage: rolloutPercentage,
            created_at: now,
          },
        };
      },
    });
    return c.json(response.body, response.status as 201);
  });

  app.get("/v1/admin/releases", async (c) => {
    await authenticateAdmin(c, "releases:read");
    const rows = await c.env.DB.prepare(
      `SELECT id, version, channel, manifest_sha256, package_sha256,
              package_size, github_repository, github_release_id,
              github_asset_id, github_asset_name, rollout_percentage,
              paused, enabled, published_at, created_at
         FROM releases ORDER BY published_at DESC LIMIT 200`,
    ).all<Record<string, unknown>>();
    return c.json({
      releases: rows.results.map((row) => ({
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
        rollout_percentage: Number(row.rollout_percentage),
        paused: Number(row.paused) === 1,
        enabled: Number(row.enabled) === 1,
        published_at: String(row.published_at),
        created_at: String(row.created_at),
      })),
    });
  });

  app.patch("/v1/admin/releases/:releaseId", async (c) => {
    const admin = await authenticateAdmin(c, "releases:write");
    const releaseId = c.req.param("releaseId");
    const request = await readJsonObject(c.req.raw);
    const enabled = parseBoolean(request.enabled, "enabled");
    const paused = parseBoolean(request.paused, "paused");
    const rolloutPercentage =
      request.rollout_percentage === undefined
        ? undefined
        : requiredInteger(request, "rollout_percentage", { minimum: 0, maximum: 100 });
    if (enabled === undefined && paused === undefined && rolloutPercentage === undefined) {
      throw new ApiError("INVALID_REQUEST", "至少需要一个发布状态字段。", { status: 400 });
    }
    const nonce = requiredString(request, "operation_nonce", { minimum: 8, maximum: 256 });
    const response = await runIdempotent(c.env, {
      scope: `admin-release-update:${admin.id}`,
      key: nonce,
      request: { releaseId, enabled, paused, rolloutPercentage },
      operation: async () => {
        const updated = await c.env.DB.prepare(
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
        await writeAudit(c.env, {
          actorType: "admin",
          actorId: admin.id,
          action: "release.update",
          targetType: "release",
          targetId: releaseId,
          result: "success",
          requestId: c.get("requestId"),
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
    return c.json(response.body, response.status as 200);
  });

  app.get("/v1/admin/diagnostics", async (c) => {
    await authenticateAdmin(c, "diagnostics:read");
    const rows = await c.env.DB.prepare(
      `SELECT id, license_id, device_id, size, sha256,
              client_version, launcher_version, status,
              submitted_at, expires_at, downloaded_at, created_at
         FROM diagnostic_submissions
        ORDER BY created_at DESC LIMIT 200`,
    ).all<Record<string, unknown>>();
    return c.json({
      diagnostics: rows.results.map((row) => ({
        submission_id: String(row.id),
        license_id: String(row.license_id),
        device_id: String(row.device_id),
        size_bytes: row.size === null ? null : Number(row.size),
        sha256: row.sha256,
        client_version: String(row.client_version),
        launcher_version: String(row.launcher_version),
        status: String(row.status),
        submitted_at: row.submitted_at,
        expires_at: String(row.expires_at),
        downloaded_at: row.downloaded_at,
        created_at: String(row.created_at),
      })),
    });
  });

  app.get("/v1/admin/diagnostics/:submissionId/content", async (c) => {
    const admin = await authenticateAdmin(c, "diagnostics:read");
    const submissionId = c.req.param("submissionId");
    const row = await c.env.DB.prepare(
      `SELECT object_key, status FROM diagnostic_submissions
        WHERE id = ? LIMIT 1`,
    )
      .bind(submissionId)
      .first<Record<string, unknown>>();
    if (row === null || row.status !== "complete") {
      throw new ApiError("DIAGNOSTIC_NOT_FOUND", "诊断包不存在或尚未完成。", {
        status: 404,
      });
    }
    const object = await c.env.DIAGNOSTICS.get(String(row.object_key));
    if (object === null) {
      throw new ApiError("DIAGNOSTIC_NOT_FOUND", "诊断对象不存在。", { status: 404 });
    }
    const now = isoNow();
    c.executionCtx.waitUntil(
      Promise.all([
        c.env.DB.prepare(
          "UPDATE diagnostic_submissions SET downloaded_at = ? WHERE id = ?",
        )
          .bind(now, submissionId)
          .run(),
        writeAudit(c.env, {
          actorType: "admin",
          actorId: admin.id,
          action: "diagnostic.download",
          targetType: "diagnostic",
          targetId: submissionId,
          result: "success",
          requestId: c.get("requestId"),
        }),
      ]).then(() => undefined),
    );
    const headers = new Headers();
    object.writeHttpMetadata(headers);
    headers.set("Content-Disposition", `attachment; filename="${submissionId}.zip"`);
    headers.set("Cache-Control", "private, no-store");
    headers.set("ETag", object.httpEtag);
    return new Response(object.body, { headers });
  });

  app.delete("/v1/admin/diagnostics/:submissionId", async (c) => {
    const admin = await authenticateAdmin(c, "diagnostics:delete");
    const submissionId = c.req.param("submissionId");
    const row = await c.env.DB.prepare(
      "SELECT object_key FROM diagnostic_submissions WHERE id = ? LIMIT 1",
    )
      .bind(submissionId)
      .first<Record<string, unknown>>();
    if (row === null) {
      throw new ApiError("DIAGNOSTIC_NOT_FOUND", "诊断提交不存在。", { status: 404 });
    }
    await c.env.DIAGNOSTICS.delete(String(row.object_key));
    await c.env.DB.prepare(
      "UPDATE diagnostic_submissions SET status = 'deleted' WHERE id = ?",
    )
      .bind(submissionId)
      .run();
    await writeAudit(c.env, {
      actorType: "admin",
      actorId: admin.id,
      action: "diagnostic.delete",
      targetType: "diagnostic",
      targetId: submissionId,
      result: "success",
      requestId: c.get("requestId"),
    });
    return c.json({ ok: true, submission_id: submissionId, status: "deleted" });
  });

  app.post("/v1/admin/contact-encryption/rotate", async (c) => {
    const admin = await authenticateAdmin(c, "contacts:rotate");
    const request = await readJsonObject(c.req.raw);
    const limit =
      request.limit === undefined
        ? 50
        : requiredInteger(request, "limit", { minimum: 1, maximum: 200 });
    const nonce = requiredString(request, "operation_nonce", {
      minimum: 8,
      maximum: 256,
    });
    const current = currentContactKey(c.env);
    const response = await runIdempotent(c.env, {
      scope: `admin-contact-rotation:${admin.id}`,
      key: nonce,
      request: { limit, currentKeyVersion: current.version },
      operation: async () => {
        const rows = await c.env.DB.prepare(
          `SELECT license_id, ciphertext, iv, encryption_key_version
             FROM license_contacts
            WHERE encryption_key_version != ?
            ORDER BY updated_at ASC
            LIMIT ?`,
        )
          .bind(current.version, limit)
          .all<Record<string, unknown>>();
        const updatedAt = isoNow();
        const statements: D1PreparedStatement[] = [];
        for (const row of rows.results) {
          const licenseId = String(row.license_id);
          const previousVersion = Number(row.encryption_key_version);
          const contacts = await decryptContacts(
            {
              ciphertext: databaseBytes(row.ciphertext, "ciphertext"),
              iv: databaseBytes(row.iv, "iv"),
              keyVersion: previousVersion,
            },
            {
              licenseId,
              encryptionKeyBase64: contactKey(c.env, previousVersion),
            },
          );
          const encrypted = await encryptContacts(contacts, {
            licenseId,
            keyVersion: current.version,
            encryptionKeyBase64: current.key,
            lookupPepper: c.env.CONTACT_LOOKUP_PEPPER,
          });
          statements.push(
            c.env.DB.prepare(
              `UPDATE license_contacts
                  SET ciphertext = ?, iv = ?, encryption_key_version = ?,
                      email_lookup_digest = ?, wechat_lookup_digest = ?,
                      other_lookup_digest = ?, updated_at = ?
                WHERE license_id = ? AND encryption_key_version = ?`,
            ).bind(
              encrypted.ciphertext,
              encrypted.iv,
              encrypted.keyVersion,
              encrypted.emailLookupDigest,
              encrypted.wechatLookupDigest,
              encrypted.otherLookupDigest,
              updatedAt,
              licenseId,
              previousVersion,
            ),
          );
        }
        if (statements.length > 0) {
          await c.env.DB.batch(statements);
        }
        const remaining = await c.env.DB.prepare(
          `SELECT COUNT(*) AS count FROM license_contacts
            WHERE encryption_key_version != ?`,
        )
          .bind(current.version)
          .first<{ count: number }>();
        await writeAudit(c.env, {
          actorType: "admin",
          actorId: admin.id,
          action: "contacts.rotate",
          result: "success",
          requestId: c.get("requestId"),
          metadata: {
            current_key_version: current.version,
            rotated_count: statements.length,
            remaining_count: Number(remaining?.count ?? 0),
          },
        });
        return {
          body: {
            ok: true,
            current_key_version: current.version,
            rotated_count: statements.length,
            remaining_count: Number(remaining?.count ?? 0),
          },
        };
      },
    });
    return c.json(response.body, response.status as 200);
  });

  app.get("/v1/admin/contact-encryption/status", async (c) => {
    await authenticateAdmin(c, "contacts:rotate");
    const current = currentContactKey(c.env);
    const rows = await c.env.DB.prepare(
      `SELECT encryption_key_version, COUNT(*) AS count
         FROM license_contacts
        GROUP BY encryption_key_version
        ORDER BY encryption_key_version`,
    ).all<Record<string, unknown>>();
    return c.json({
      current_key_version: current.version,
      records_by_version: rows.results.map((row) => ({
        key_version: Number(row.encryption_key_version),
        count: Number(row.count),
      })),
    });
  });
}
