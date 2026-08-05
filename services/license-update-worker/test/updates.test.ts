import { describe, expect, it } from "vitest";

import { ApiError } from "../src/http";
import { d1BlobBytes } from "../src/updates";

describe("D1 BLOB decoding", () => {
  it("accepts ArrayBuffer and typed-array values", () => {
    const buffer = Uint8Array.from([1, 2, 3]).buffer;
    expect([...d1BlobBytes(buffer, "manifest")]).toEqual([1, 2, 3]);
    expect([...d1BlobBytes(Uint8Array.from([4, 5]), "signature")]).toEqual([
      4,
      5,
    ]);
  });

  it("accepts the plain byte arrays returned by local D1", () => {
    expect([...d1BlobBytes([0, 127, 255], "manifest")]).toEqual([
      0,
      127,
      255,
    ]);
  });

  it("rejects strings and out-of-range array values", () => {
    for (const value of ["AQID", [0, 256], [1, -1], [1, 1.5]]) {
      try {
        d1BlobBytes(value, "manifest");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).code).toBe("RELEASE_STATE_INVALID");
        continue;
      }
      throw new Error("invalid D1 BLOB value was accepted");
    }
  });
});
