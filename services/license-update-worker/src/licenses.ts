import type { Hono } from "hono";

import { authenticateDevice } from "./auth";
import {
  bytesToBase64,
  createDeviceToken,
  hmacSha256Hex,
  licenseKeyHint,
  normalizeLicenseKey,
  randomId,
  signOfflineLease,
} from "./crypto";
import {
  ApiError,
  optionalString,
  readJsonObject,
  requiredString,
} from "./http";
import {
  addDays,
  enforceRateLimit,
  isoNow,
  runIdempotent,
  writeAudit,
} from "./service";
import type { DeviceRow, Env, LicenseRow } from "./types";

interface WorkerVariables {
  requestId: string;
}

type WorkerApp = Hono<{ Bindings: Env; Variables: WorkerVariables }>;

function normalizedVersion(value: string, name: string): string {
  if (!/^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/u.test(value)) {
    throw new ApiError("INVALID_REQUEST", `${name} 不是有效版本号。`, {
      status: 400,
    });
  }
  return value;
}

function licenseFromRow(row: Record<string, unknown>): LicenseRow {
  return {
    id: String(row.id),
    key_digest: String(row.key_digest),
    key_hint: String(row.key_hint),
    status: row.status as LicenseRow["status"],
    max_devices: Number(row.max_devices),
    release_channel: row.release_channel as LicenseRow["release_channel"],
    revision: Number(row.revision),
    created_at: String(row.created_at),
    updated_at: String(row.updated_at),
    suspended_at: row.suspended_at === null ? null : String(row.suspended_at),
    revoked_at: row.revoked_at === null ? null : String(row.revoked_at),
    created_by_admin_id:
      row.created_by_admin_id === null ? null : String(row.created_by_admin_id),
  };
}

function deviceFromRow(row: Record<string, unknown>): DeviceRow {
  return {
    id: String(row.id),
    license_id: String(row.license_id),
    client_install_id_digest: String(row.client_install_id_digest),
    fingerprint_digest:
      row.fingerprint_digest === null ? null : String(row.fingerprint_digest),
    display_name: String(row.display_name),
    status: row.status as DeviceRow["status"],
    token_id: String(row.token_id),
    token_secret_digest: String(row.token_secret_digest),
    token_version: Number(row.token_version),
    device_revision: Number(row.device_revision),
    first_activated_at: String(row.first_activated_at),
    last_validated_at:
      row.last_validated_at === null ? null : String(row.last_validated_at),
    last_app_version:
      row.last_app_version === null ? null : String(row.last_app_version),
    last_launcher_version:
      row.last_launcher_version === null
        ? null
        : String(row.last_launcher_version),
    disabled_at: row.disabled_at === null ? null : String(row.disabled_at),
    unbound_at: row.unbound_at === null ? null : String(row.unbound_at),
  };
}

async function issueLease(
  env: Env,
  license: LicenseRow,
  device: DeviceRow,
  now = new Date(),
): Promise<{
  lease_content_base64: string;
  lease_signature_base64: string;
  server_time: string;
  offline_until: string;
}> {
  const issuedAt = isoNow(now);
  const offlineUntil = isoNow(addDays(now, 7));
  const signed = await signOfflineLease(
    {
      schema_version: 1,
      license_id: license.id,
      device_id: device.id,
      status: license.status,
      license_revision: license.revision,
      device_revision: device.device_revision,
      issued_at: issuedAt,
      offline_until: offlineUntil,
      nonce: randomId("lease_", 18),
      key_id: env.LEASE_SIGNING_KEY_ID,
    },
    env.LEASE_SIGNING_PRIVATE_KEY,
  );
  return {
    lease_content_base64: bytesToBase64(signed.content),
    lease_signature_base64: bytesToBase64(signed.signature),
    server_time: issuedAt,
    offline_until: offlineUntil,
  };
}

function assertActiveLicense(license: LicenseRow): void {
  if (license.status === "suspended") {
    throw new ApiError("LICENSE_SUSPENDED", "许可证已暂停。", { status: 403 });
  }
  if (license.status === "revoked") {
    throw new ApiError("LICENSE_REVOKED", "许可证已吊销。", { status: 403 });
  }
}

async function activeDeviceCount(env: Env, licenseId: string): Promise<number> {
  const row = await env.DB.prepare(
    "SELECT COUNT(*) AS count FROM devices WHERE license_id = ? AND status = 'active'",
  )
    .bind(licenseId)
    .first<{ count: number }>();
  return Number(row?.count ?? 0);
}

async function findDevice(env: Env, deviceId: string): Promise<DeviceRow | null> {
  const row = await env.DB.prepare(
    `SELECT id, license_id, client_install_id_digest, fingerprint_digest,
            display_name, status, token_id, token_secret_digest,
            token_version, device_revision, first_activated_at,
            last_validated_at, last_app_version, last_launcher_version,
            disabled_at, unbound_at
       FROM devices
      WHERE id = ?
      LIMIT 1`,
  )
    .bind(deviceId)
    .first<Record<string, unknown>>();
  return row === null ? null : deviceFromRow(row);
}

export function registerLicenseRoutes(app: WorkerApp): void {
  app.post("/v1/licenses/activate", async (c) => {
    await enforceRateLimit(c, {
      name: "license-activate",
      maximum: 12,
      windowSeconds: 60,
    });
    const request = await readJsonObject(c.req.raw);
    const licenseKey = requiredString(request, "license_key", {
      minimum: 16,
      maximum: 128,
    });
    const deviceId = requiredString(request, "device_id", {
      minimum: 12,
      maximum: 160,
      pattern: /^dev_[A-Za-z0-9_-]+$/u,
    });
    const fingerprint = requiredString(request, "device_fingerprint", {
      minimum: 64,
      maximum: 64,
      pattern: /^[0-9a-f]{64}$/iu,
    });
    const deviceName = requiredString(request, "device_name", {
      maximum: 64,
    });
    const appVersion = normalizedVersion(
      requiredString(request, "app_version", { maximum: 64 }),
      "app_version",
    );
    const launcherVersion = normalizedVersion(
      requiredString(request, "launcher_version", { maximum: 64 }),
      "launcher_version",
    );

    let normalizedKey: string;
    try {
      normalizedKey = normalizeLicenseKey(licenseKey);
    } catch (error) {
      throw new ApiError("LICENSE_NOT_FOUND", "许可证密钥无效。", {
        status: 404,
        cause: error,
      });
    }
    const keyDigest = await hmacSha256Hex(
      c.env.LICENSE_KEY_PEPPER,
      `license-key\u0000${normalizedKey}`,
    );
    const licenseRow = await c.env.DB.prepare(
      `SELECT id, key_digest, key_hint, status, max_devices,
              release_channel, revision, created_at, updated_at,
              suspended_at, revoked_at, created_by_admin_id
         FROM licenses
        WHERE key_digest = ?
        LIMIT 1`,
    )
      .bind(keyDigest)
      .first<Record<string, unknown>>();
    if (licenseRow === null) {
      throw new ApiError("LICENSE_NOT_FOUND", "许可证密钥无效。", {
        status: 404,
      });
    }
    const license = licenseFromRow(licenseRow);
    assertActiveLicense(license);

    const installDigest = await hmacSha256Hex(
      c.env.DEVICE_TOKEN_PEPPER,
      `install-id\u0000${deviceId}`,
    );
    const fingerprintDigest = await hmacSha256Hex(
      c.env.DEVICE_TOKEN_PEPPER,
      `fingerprint\u0000${fingerprint.toLowerCase()}`,
    );
    const token = createDeviceToken();
    const tokenSecretDigest = await hmacSha256Hex(
      c.env.DEVICE_TOKEN_PEPPER,
      token.tokenSecret,
    );
    const now = isoNow();
    const existing = await findDevice(c.env, deviceId);
    if (existing !== null && existing.license_id !== license.id) {
      throw new ApiError("DEVICE_ID_CONFLICT", "设备标识已绑定到其他许可证。", {
        status: 409,
      });
    }

    if (existing === null) {
      const inserted = await c.env.DB.prepare(
        `INSERT INTO devices (
           id, license_id, client_install_id_digest, fingerprint_digest,
           display_name, status, token_id, token_secret_digest,
           token_version, device_revision, first_activated_at,
           last_validated_at, last_app_version, last_launcher_version
         )
         SELECT ?, l.id, ?, ?, ?, 'active', ?, ?, 1, 1, ?, ?, ?, ?
           FROM licenses l
          WHERE l.id = ?
            AND (
              SELECT COUNT(*) FROM devices d
               WHERE d.license_id = l.id AND d.status = 'active'
            ) < l.max_devices`,
      )
        .bind(
          deviceId,
          installDigest,
          fingerprintDigest,
          deviceName,
          token.tokenId,
          tokenSecretDigest,
          now,
          now,
          appVersion,
          launcherVersion,
          license.id,
        )
        .run();
      if (Number(inserted.meta.changes ?? 0) !== 1) {
        throw new ApiError("DEVICE_LIMIT_REACHED", "许可证设备数量已达上限。", {
          status: 409,
          details: { maximum_devices: license.max_devices },
        });
      }
    } else if (existing.status === "disabled") {
      throw new ApiError("DEVICE_DISABLED", "当前设备已停用。", { status: 403 });
    } else if (existing.status === "unbound") {
      const rebound = await c.env.DB.prepare(
        `UPDATE devices
            SET client_install_id_digest = ?, fingerprint_digest = ?,
                display_name = ?, status = 'active', token_id = ?,
                token_secret_digest = ?, token_version = token_version + 1,
                device_revision = device_revision + 1,
                last_validated_at = ?, last_app_version = ?,
                last_launcher_version = ?, unbound_at = NULL
          WHERE id = ? AND license_id = ? AND status = 'unbound'
            AND (
              SELECT COUNT(*) FROM devices d
               WHERE d.license_id = ? AND d.status = 'active'
            ) < ?`,
      )
        .bind(
          installDigest,
          fingerprintDigest,
          deviceName,
          token.tokenId,
          tokenSecretDigest,
          now,
          appVersion,
          launcherVersion,
          deviceId,
          license.id,
          license.id,
          license.max_devices,
        )
        .run();
      if (Number(rebound.meta.changes ?? 0) !== 1) {
        throw new ApiError("DEVICE_LIMIT_REACHED", "许可证设备数量已达上限。", {
          status: 409,
          details: { maximum_devices: license.max_devices },
        });
      }
    } else {
      await c.env.DB.prepare(
        `UPDATE devices
            SET client_install_id_digest = ?, fingerprint_digest = ?,
                display_name = ?, token_id = ?, token_secret_digest = ?,
                token_version = token_version + 1,
                device_revision = device_revision + 1,
                last_validated_at = ?, last_app_version = ?,
                last_launcher_version = ?
          WHERE id = ? AND license_id = ? AND status = 'active'`,
      )
        .bind(
          installDigest,
          fingerprintDigest,
          deviceName,
          token.tokenId,
          tokenSecretDigest,
          now,
          appVersion,
          launcherVersion,
          deviceId,
          license.id,
        )
        .run();
    }

    const device = await findDevice(c.env, deviceId);
    if (device === null || device.status !== "active") {
      throw new ApiError("ACTIVATION_FAILED", "设备激活状态未能确认。", {
        status: 500,
        retryable: true,
      });
    }
    const count = await activeDeviceCount(c.env, license.id);
    const lease = await issueLease(c.env, license, device);
    await writeAudit(c.env, {
      actorType: "license",
      actorId: license.id,
      action: "device.activate",
      targetType: "device",
      targetId: device.id,
      result: "success",
      requestId: c.get("requestId"),
      metadata: {
        device_count: count,
        maximum_devices: license.max_devices,
        app_version: appVersion,
        launcher_version: launcherVersion,
      },
    });
    return c.json(
      {
        license_id: license.id,
        license_hint: licenseKeyHint(licenseKey),
        device_id: device.id,
        device_token: token.value,
        device_count: count,
        maximum_devices: license.max_devices,
        ...lease,
      },
      200,
    );
  });

  app.post("/v1/devices/validate", async (c) => {
    const authenticated = await authenticateDevice(c);
    await enforceRateLimit(c, {
      name: "device-validate",
      maximum: 30,
      windowSeconds: 60,
      identity: authenticated.device.id,
    });
    const request = await readJsonObject(c.req.raw);
    const appVersion = normalizedVersion(
      requiredString(request, "app_version", { maximum: 64 }),
      "app_version",
    );
    const launcherVersion = normalizedVersion(
      requiredString(request, "launcher_version", { maximum: 64 }),
      "launcher_version",
    );
    const now = isoNow();
    await c.env.DB.prepare(
      `UPDATE devices
          SET last_validated_at = ?, last_app_version = ?,
              last_launcher_version = ?
        WHERE id = ? AND status = 'active'`,
    )
      .bind(now, appVersion, launcherVersion, authenticated.device.id)
      .run();
    const device: DeviceRow = {
      ...authenticated.device,
      last_validated_at: now,
      last_app_version: appVersion,
      last_launcher_version: launcherVersion,
    };
    const lease = await issueLease(c.env, authenticated.license, device);
    await writeAudit(c.env, {
      actorType: "device",
      actorId: device.id,
      action: "device.validate",
      targetType: "license",
      targetId: authenticated.license.id,
      result: "success",
      requestId: c.get("requestId"),
      metadata: {
        app_version: appVersion,
        launcher_version: launcherVersion,
      },
    });
    return c.json({
      license_id: authenticated.license.id,
      device_id: device.id,
      ...lease,
    });
  });

  app.get("/v1/devices", async (c) => {
    const authenticated = await authenticateDevice(c);
    const rows = await c.env.DB.prepare(
      `SELECT id, display_name, status, last_validated_at,
              last_app_version, last_launcher_version
         FROM devices
        WHERE license_id = ?
        ORDER BY first_activated_at ASC`,
    )
      .bind(authenticated.license.id)
      .all<Record<string, unknown>>();
    return c.json({
      devices: rows.results.map((row) => ({
        device_id: String(row.id),
        display_name: String(row.display_name),
        status: String(row.status),
        is_current: String(row.id) === authenticated.device.id,
        last_validated_at:
          row.last_validated_at === null ? null : String(row.last_validated_at),
        last_app_version:
          row.last_app_version === null ? null : String(row.last_app_version),
        last_launcher_version:
          row.last_launcher_version === null
            ? null
            : String(row.last_launcher_version),
      })),
    });
  });

  app.patch("/v1/devices/:deviceId", async (c) => {
    const authenticated = await authenticateDevice(c);
    const targetDeviceId = requiredString(
      { device_id: c.req.param("deviceId") },
      "device_id",
      { maximum: 160 },
    );
    const request = await readJsonObject(c.req.raw);
    const displayName = requiredString(request, "display_name", { maximum: 64 });
    const nonce = requiredString(request, "operation_nonce", {
      minimum: 8,
      maximum: 256,
    });
    const response = await runIdempotent(c.env, {
      scope: `device-rename:${authenticated.license.id}`,
      key: nonce,
      request: { targetDeviceId, displayName },
      operation: async () => {
        const updated = await c.env.DB.prepare(
          `UPDATE devices
              SET display_name = ?, device_revision = device_revision + 1
            WHERE id = ? AND license_id = ? AND status = 'active'`,
        )
          .bind(displayName, targetDeviceId, authenticated.license.id)
          .run();
        if (Number(updated.meta.changes ?? 0) !== 1) {
          throw new ApiError("DEVICE_NOT_FOUND", "目标设备不存在或不可修改。", {
            status: 404,
          });
        }
        await writeAudit(c.env, {
          actorType: "device",
          actorId: authenticated.device.id,
          action: "device.rename",
          targetType: "device",
          targetId: targetDeviceId,
          result: "success",
          requestId: c.get("requestId"),
        });
        return { body: { ok: true, device_id: targetDeviceId } };
      },
    });
    return c.json(response.body, response.status as 200);
  });

  app.post("/v1/devices/:deviceId/unbind", async (c) => {
    const authenticated = await authenticateDevice(c);
    const targetDeviceId = requiredString(
      { device_id: c.req.param("deviceId") },
      "device_id",
      { maximum: 160 },
    );
    if (targetDeviceId === authenticated.device.id) {
      throw new ApiError("CURRENT_DEVICE_UNBIND_DENIED", "当前设备不能解绑自身。", {
        status: 400,
      });
    }
    const request = await readJsonObject(c.req.raw);
    const bodyTarget = optionalString(request, "target_device_id", 160);
    if (bodyTarget !== undefined && bodyTarget !== targetDeviceId) {
      throw new ApiError("INVALID_REQUEST", "路径和正文中的设备标识不一致。", {
        status: 400,
      });
    }
    const nonce = requiredString(request, "operation_nonce", {
      minimum: 8,
      maximum: 256,
    });
    const response = await runIdempotent(c.env, {
      scope: `device-unbind:${authenticated.license.id}`,
      key: nonce,
      request: { targetDeviceId },
      operation: async () => {
        const now = isoNow();
        const updated = await c.env.DB.prepare(
          `UPDATE devices
              SET status = 'unbound', unbound_at = ?,
                  token_version = token_version + 1,
                  device_revision = device_revision + 1
            WHERE id = ? AND license_id = ? AND status = 'active'`,
        )
          .bind(now, targetDeviceId, authenticated.license.id)
          .run();
        if (Number(updated.meta.changes ?? 0) !== 1) {
          throw new ApiError("DEVICE_NOT_FOUND", "目标设备不存在或已解绑。", {
            status: 404,
          });
        }
        await writeAudit(c.env, {
          actorType: "device",
          actorId: authenticated.device.id,
          action: "device.unbind",
          targetType: "device",
          targetId: targetDeviceId,
          result: "success",
          requestId: c.get("requestId"),
        });
        return {
          body: { ok: true, unbound_device_id: targetDeviceId },
        };
      },
    });
    return c.json(response.body, response.status as 200);
  });
}
