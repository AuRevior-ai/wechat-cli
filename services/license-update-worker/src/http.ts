import type { Context } from "hono";

import type { Env, WorkerVariables } from "./types";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;
  readonly details: Record<string, unknown> | undefined;

  constructor(
    code: string,
    message: string,
    options: {
      status?: number;
      retryable?: boolean;
      details?: Record<string, unknown>;
      cause?: unknown;
    } = {},
  ) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause });
    this.name = "ApiError";
    this.code = code;
    this.status = options.status ?? 400;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

export function requestId(request: Request): string {
  const provided = request.headers.get("X-Request-Id")?.trim();
  if (provided !== undefined && /^[A-Za-z0-9._:-]{8,128}$/u.test(provided)) {
    return provided;
  }
  return crypto.randomUUID();
}

export function apiErrorResponse(
  c: Context<{ Bindings: Env; Variables: WorkerVariables }, any, any>,
  error: ApiError,
  id: string,
): Response {
  const body: Record<string, unknown> = {
    code: error.code,
    message: error.message,
    retryable: error.retryable,
    request_id: id,
  };
  if (error.details !== undefined) {
    body.details = error.details;
  }
  return c.json({ error: body }, error.status as 400);
}

export async function readJsonObject(
  request: Request,
  options: { maximumBytes?: number } = {},
): Promise<Record<string, unknown>> {
  const maximumBytes = options.maximumBytes ?? 64 * 1024;
  const lengthHeader = request.headers.get("Content-Length");
  if (lengthHeader !== null) {
    const length = Number.parseInt(lengthHeader, 10);
    if (!Number.isFinite(length) || length < 0 || length > maximumBytes) {
      throw new ApiError("REQUEST_TOO_LARGE", "请求正文过大。", { status: 413 });
    }
  }
  const raw = await request.arrayBuffer();
  if (raw.byteLength > maximumBytes) {
    throw new ApiError("REQUEST_TOO_LARGE", "请求正文过大。", { status: 413 });
  }
  let value: unknown;
  try {
    value = JSON.parse(new TextDecoder().decode(raw));
  } catch (error) {
    throw new ApiError("INVALID_JSON", "请求正文不是有效 JSON。", {
      status: 400,
      cause: error,
    });
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ApiError("INVALID_JSON", "请求 JSON 根节点必须是对象。", {
      status: 400,
    });
  }
  return value as Record<string, unknown>;
}

export function requiredString(
  data: Record<string, unknown>,
  name: string,
  options: { minimum?: number; maximum?: number; pattern?: RegExp } = {},
): string {
  const value = data[name];
  if (typeof value !== "string") {
    throw new ApiError("INVALID_REQUEST", `${name} 必须是字符串。`, { status: 400 });
  }
  const trimmed = value.trim();
  const minimum = options.minimum ?? 1;
  const maximum = options.maximum ?? 4096;
  if (trimmed.length < minimum || trimmed.length > maximum) {
    throw new ApiError("INVALID_REQUEST", `${name} 长度无效。`, { status: 400 });
  }
  if (options.pattern !== undefined && !options.pattern.test(trimmed)) {
    throw new ApiError("INVALID_REQUEST", `${name} 格式无效。`, { status: 400 });
  }
  return trimmed;
}

export function optionalString(
  data: Record<string, unknown>,
  name: string,
  maximum = 2048,
): string | undefined {
  const value = data[name];
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (typeof value !== "string" || value.length > maximum) {
    throw new ApiError("INVALID_REQUEST", `${name} 格式无效。`, { status: 400 });
  }
  const trimmed = value.trim();
  return trimmed.length === 0 ? undefined : trimmed;
}

export function requiredInteger(
  data: Record<string, unknown>,
  name: string,
  options: { minimum?: number; maximum?: number } = {},
): number {
  const value = data[name];
  if (!Number.isInteger(value)) {
    throw new ApiError("INVALID_REQUEST", `${name} 必须是整数。`, { status: 400 });
  }
  const integer = value as number;
  if (options.minimum !== undefined && integer < options.minimum) {
    throw new ApiError("INVALID_REQUEST", `${name} 小于允许范围。`, { status: 400 });
  }
  if (options.maximum !== undefined && integer > options.maximum) {
    throw new ApiError("INVALID_REQUEST", `${name} 超出允许范围。`, { status: 400 });
  }
  return integer;
}
