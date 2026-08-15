import { describe, expect, it } from "vitest";

import { AccessJwtVerifier, fetchAccessJwks } from "../src/access_identity";


describe("shared Access identity verifier module", () => {
  it("exports the existing strict JWT verifier and JWKS fetcher", () => {
    expect(AccessJwtVerifier).toBeTypeOf("function");
    expect(fetchAccessJwks).toBeTypeOf("function");
  });
});
