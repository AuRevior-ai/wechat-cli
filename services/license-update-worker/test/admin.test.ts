import { describe, expect, it } from "vitest";

import * as adminModule from "../src/admin";
import { ApiError } from "../src/http";
import type { Env } from "../src/types";

interface QueryState {
  sql: string[];
  bindings: unknown[][];
}

function releaseLookupEnv(existingManifestSha256: string | null): {
  env: Env;
  state: QueryState;
} {
  const state: QueryState = { sql: [], bindings: [] };
  const db = {
    prepare(sql: string) {
      state.sql.push(sql);
      let bound: unknown[] = [];
      return {
        bind(...values: unknown[]) {
          bound = values;
          state.bindings.push(values);
          return this;
        },
        async first<T>() {
          if (!sql.includes("FROM releases")) {
            throw new Error(`unexpected query: ${sql}`);
          }
          if (existingManifestSha256 === null) {
            return null;
          }
          return {
            id: "rel_existing",
            manifest_sha256: existingManifestSha256,
          } as T;
        },
      };
    },
  } as unknown as D1Database;
  return { env: { DB: db } as Env, state };
}

function immutabilityAssertion(): (
  env: Env,
  channel: "stable" | "beta",
  version: string,
  manifestSha256: string,
) => Promise<void> {
  const candidate = (
    adminModule as unknown as {
      assertReleaseVersionImmutable?: (
        env: Env,
        channel: "stable" | "beta",
        version: string,
        manifestSha256: string,
      ) => Promise<void>;
    }
  ).assertReleaseVersionImmutable;
  expect(candidate).toBeTypeOf("function");
  return candidate as NonNullable<typeof candidate>;
}

describe("release version immutability", () => {
  it("rejects the same channel and version with a different manifest", async () => {
    const { env, state } = releaseLookupEnv("a".repeat(64));
    const assertImmutable = immutabilityAssertion();

    await expect(
      assertImmutable(env, "stable", "0.6.0", "b".repeat(64)),
    ).rejects.toMatchObject({
      code: "RELEASE_VERSION_IMMUTABLE",
      status: 409,
    } satisfies Partial<ApiError>);
    expect(state.sql).toHaveLength(1);
    expect(state.bindings[0]).toEqual(["stable", "0.6.0"]);
  });

  it("allows an exact-manifest replay or a previously unused version", async () => {
    const exact = releaseLookupEnv("a".repeat(64));
    const absent = releaseLookupEnv(null);
    const assertImmutable = immutabilityAssertion();

    await expect(
      assertImmutable(exact.env, "stable", "0.6.0", "a".repeat(64)),
    ).resolves.toBeUndefined();
    await expect(
      assertImmutable(absent.env, "beta", "0.7.0", "c".repeat(64)),
    ).resolves.toBeUndefined();
  });
});
