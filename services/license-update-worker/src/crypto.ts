const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

export function bytesToBase64(bytes: ArrayBuffer | Uint8Array): string {
  const value = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let binary = "";
  for (let index = 0; index < value.length; index += 0x8000) {
    binary += String.fromCharCode(...value.subarray(index, index + 0x8000));
  }
  return btoa(binary);
}

export function base64ToBytes(
  value: string,
  expectedLength?: number,
): Uint8Array<ArrayBuffer> {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error("base64 value is required");
  }
  let binary: string;
  try {
    binary = atob(value);
  } catch (error) {
    throw new Error("base64 value is invalid", { cause: error });
  }
  const bytes: Uint8Array<ArrayBuffer> = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  if (expectedLength !== undefined && bytes.length !== expectedLength) {
    throw new Error(`decoded value must contain ${expectedLength} bytes`);
  }
  return bytes;
}

export function bytesToBase64Url(bytes: Uint8Array): string {
  return bytesToBase64(bytes)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/u, "");
}

export function randomToken(bytes = 32): string {
  if (!Number.isInteger(bytes) || bytes < 16 || bytes > 128) {
    throw new Error("random token length must be between 16 and 128 bytes");
  }
  const value = new Uint8Array(bytes);
  crypto.getRandomValues(value);
  return bytesToBase64Url(value);
}

export function randomId(prefix: string, bytes = 16): string {
  if (!/^[a-z][a-z0-9_]{1,20}_$/u.test(prefix)) {
    throw new Error("ID prefix is invalid");
  }
  return prefix + randomToken(bytes);
}

export function normalizeLicenseKey(value: string): string {
  if (typeof value !== "string") {
    throw new Error("license key must be text");
  }
  const compact = value
    .normalize("NFKC")
    .toUpperCase()
    .replace(/[^A-Z0-9]/gu, "");
  if (!compact.startsWith("WCL") || compact.length < 19 || compact.length > 80) {
    throw new Error("license key format is invalid");
  }
  return compact;
}

export function licenseKeyHint(value: string): string {
  const normalized = normalizeLicenseKey(value);
  return normalized.slice(-4);
}

function formatLicenseKeyEntropy(bytes: Uint8Array): string {
  if (bytes.length < 16) {
    throw new Error("license key entropy must contain at least 16 bytes");
  }
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const groups: string[] = [];
  for (let group = 0; group < 4; group += 1) {
    let value = "";
    for (let offset = 0; offset < 4; offset += 1) {
      const byte = bytes[group * 4 + offset];
      if (byte === undefined) {
        throw new Error("license key entropy generation failed");
      }
      value += alphabet[byte % alphabet.length];
    }
    groups.push(value);
  }
  return `WCL-${groups.join("-")}`;
}

export function createLicenseKey(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return formatLicenseKeyEntropy(bytes);
}

async function importHmacKey(secret: string): Promise<CryptoKey> {
  if (typeof secret !== "string" || secret.length < 16) {
    throw new Error("HMAC secret is missing or too short");
  }
  return crypto.subtle.importKey(
    "raw",
    toArrayBuffer(textEncoder.encode(secret)),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
}

export async function hmacSha256Bytes(
  secret: string,
  value: string,
): Promise<Uint8Array<ArrayBuffer>> {
  const key = await importHmacKey(secret);
  const digest = await crypto.subtle.sign(
    "HMAC",
    key,
    toArrayBuffer(textEncoder.encode(value)),
  );
  return new Uint8Array(digest) as Uint8Array<ArrayBuffer>;
}

export async function hmacSha256Hex(secret: string, value: string): Promise<string> {
  const digest = await hmacSha256Bytes(secret, value);
  return [...digest]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export async function deriveLicenseKey(
  secret: string,
  context: string,
): Promise<string> {
  const entropy = await hmacSha256Bytes(
    secret,
    `license-key-generation-v1\u0000${context}`,
  );
  return formatLicenseKeyEntropy(entropy);
}

export async function deriveOpaqueId(
  prefix: string,
  secret: string,
  context: string,
): Promise<string> {
  if (!/^[a-z][a-z0-9_]{1,20}_$/u.test(prefix)) {
    throw new Error("ID prefix is invalid");
  }
  const entropy = await hmacSha256Bytes(
    secret,
    `opaque-id-generation-v1\u0000${prefix}\u0000${context}`,
  );
  return prefix + bytesToBase64Url(entropy.subarray(0, 18));
}

function toArrayBuffer(value: ArrayBuffer | Uint8Array): ArrayBuffer {
  if (value instanceof ArrayBuffer) {
    return value;
  }
  const copy: Uint8Array<ArrayBuffer> = new Uint8Array(value.byteLength);
  copy.set(value);
  return copy.buffer;
}

export async function sha256Hex(value: ArrayBuffer | Uint8Array | string): Promise<string> {
  const input =
    typeof value === "string"
      ? toArrayBuffer(textEncoder.encode(value))
      : toArrayBuffer(value);
  const digest = await crypto.subtle.digest("SHA-256", input);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function constantTimeEqual(left: string, right: string): boolean {
  const leftBytes = textEncoder.encode(left);
  const rightBytes = textEncoder.encode(right);
  let difference = leftBytes.length ^ rightBytes.length;
  const maximum = Math.max(leftBytes.length, rightBytes.length);
  for (let index = 0; index < maximum; index += 1) {
    difference |= (leftBytes[index] ?? 0) ^ (rightBytes[index] ?? 0);
  }
  return difference === 0;
}

export interface DeviceTokenParts {
  tokenId: string;
  tokenSecret: string;
}

export function createDeviceToken(): DeviceTokenParts & { value: string } {
  const tokenId = `tk_${randomToken(16)}`;
  const tokenSecret = randomToken(32);
  return {
    tokenId,
    tokenSecret,
    value: `wcdt_${tokenId}.${tokenSecret}`,
  };
}

export function parseDeviceToken(value: string): DeviceTokenParts {
  const match = /^wcdt_(tk_[A-Za-z0-9_-]{12,64})\.([A-Za-z0-9_-]{32,256})$/u.exec(
    value,
  );
  if (match === null || match[1] === undefined || match[2] === undefined) {
    throw new Error("device token format is invalid");
  }
  return { tokenId: match[1], tokenSecret: match[2] };
}

export interface AdminTokenParts {
  tokenId: string;
  tokenSecret: string;
}

export function parseAdminToken(value: string): AdminTokenParts {
  const match = /^wcadmin_(adm_[A-Za-z0-9_-]{12,64})\.([A-Za-z0-9_-]{32,256})$/u.exec(
    value,
  );
  if (match === null || match[1] === undefined || match[2] === undefined) {
    throw new Error("admin token format is invalid");
  }
  return { tokenId: match[1], tokenSecret: match[2] };
}

export function parseDownloadTicket(value: string): { ticketId: string; secret: string } {
  const match = /^dlt_(dl_[A-Za-z0-9_-]{12,64})\.([A-Za-z0-9_-]{32,256})$/u.exec(
    value,
  );
  if (match === null || match[1] === undefined || match[2] === undefined) {
    throw new Error("download ticket format is invalid");
  }
  return { ticketId: match[1], secret: match[2] };
}

export function createDownloadTicket(): {
  ticketId: string;
  secret: string;
  value: string;
} {
  const ticketId = `dl_${randomToken(16)}`;
  const secret = randomToken(32);
  return { ticketId, secret, value: `dlt_${ticketId}.${secret}` };
}

function normalizeContact(value: string | undefined): string | undefined {
  if (value === undefined) {
    return undefined;
  }
  const normalized = value.normalize("NFKC").trim().toLowerCase();
  return normalized.length > 0 ? normalized : undefined;
}

export interface LicenseContacts {
  email?: string;
  wechat?: string;
  other?: string;
  notes?: string;
}

export interface EncryptedContacts {
  ciphertext: Uint8Array<ArrayBuffer>;
  iv: Uint8Array<ArrayBuffer>;
  keyVersion: number;
  emailLookupDigest: string | null;
  wechatLookupDigest: string | null;
  otherLookupDigest: string | null;
}

async function importAesKey(base64Key: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    base64ToBytes(base64Key, 32),
    { name: "AES-GCM" },
    false,
    ["encrypt", "decrypt"],
  );
}

function contactAad(
  licenseId: string,
  keyVersion: number,
): Uint8Array<ArrayBuffer> {
  return textEncoder.encode(
    JSON.stringify({
      schema_version: 1,
      license_id: licenseId,
      encryption_key_version: keyVersion,
    }),
  );
}

export async function encryptContacts(
  contacts: LicenseContacts,
  options: {
    licenseId: string;
    keyVersion: number;
    encryptionKeyBase64: string;
    lookupPepper: string;
  },
): Promise<EncryptedContacts> {
  if (!Number.isInteger(options.keyVersion) || options.keyVersion < 1) {
    throw new Error("contact encryption key version is invalid");
  }
  const payload: LicenseContacts = {};
  for (const field of ["email", "wechat", "other", "notes"] as const) {
    const value = contacts[field];
    if (value !== undefined) {
      if (typeof value !== "string" || value.length > 2048) {
        throw new Error(`contact field ${field} is invalid`);
      }
      const trimmed = value.trim();
      if (trimmed.length > 0) {
        payload[field] = trimmed;
      }
    }
  }
  const iv: Uint8Array<ArrayBuffer> = new Uint8Array(12);
  crypto.getRandomValues(iv);
  const key = await importAesKey(options.encryptionKeyBase64);
  const plaintext = textEncoder.encode(JSON.stringify(payload));
  const ciphertext = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv: iv.buffer,
      additionalData: contactAad(options.licenseId, options.keyVersion).buffer,
      tagLength: 128,
    },
    key,
    plaintext,
  );

  const lookup = async (value: string | undefined): Promise<string | null> => {
    const normalized = normalizeContact(value);
    return normalized === undefined
      ? null
      : hmacSha256Hex(options.lookupPepper, normalized);
  };
  return {
    ciphertext: new Uint8Array(ciphertext),
    iv,
    keyVersion: options.keyVersion,
    emailLookupDigest: await lookup(payload.email),
    wechatLookupDigest: await lookup(payload.wechat),
    otherLookupDigest: await lookup(payload.other),
  };
}

export async function decryptContacts(
  encrypted: Pick<EncryptedContacts, "ciphertext" | "iv" | "keyVersion">,
  options: { licenseId: string; encryptionKeyBase64: string },
): Promise<LicenseContacts> {
  const key = await importAesKey(options.encryptionKeyBase64);
  const plaintext = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: toArrayBuffer(encrypted.iv),
      additionalData: contactAad(options.licenseId, encrypted.keyVersion).buffer,
      tagLength: 128,
    },
    key,
    toArrayBuffer(encrypted.ciphertext),
  );
  const value: unknown = JSON.parse(textDecoder.decode(plaintext));
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("decrypted contacts are invalid");
  }
  return value as LicenseContacts;
}

export interface OfflineLeasePayload {
  schema_version: 1;
  license_id: string;
  device_id: string;
  status: "active" | "suspended" | "revoked";
  license_revision: number;
  device_revision: number;
  issued_at: string;
  offline_until: string;
  nonce: string;
  key_id: string;
}

export async function signOfflineLease(
  payload: OfflineLeasePayload,
  privateKeyPkcs8Base64: string,
): Promise<{ content: Uint8Array; signature: Uint8Array }> {
  const content = textEncoder.encode(JSON.stringify(payload));
  const key = await crypto.subtle.importKey(
    "pkcs8",
    base64ToBytes(privateKeyPkcs8Base64).buffer,
    { name: "Ed25519" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "Ed25519",
    key,
    toArrayBuffer(content),
  );
  return {
    content,
    signature: new Uint8Array(signature) as Uint8Array<ArrayBuffer>,
  };
}

export function rolloutBucket(seed: string, licenseId: string, deviceId: string): Promise<number> {
  return sha256Hex(`${seed}\u0000${licenseId}\u0000${deviceId}`).then((digest) =>
    Number.parseInt(digest.slice(0, 8), 16) % 100,
  );
}
