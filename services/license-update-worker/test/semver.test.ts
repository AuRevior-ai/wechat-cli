import { describe, expect, it } from "vitest";

import {
  compareSemanticVersions,
  parseSemanticVersion,
} from "../src/semver";

describe("semantic version parsing", () => {
  it("parses release and prerelease values", () => {
    expect(parseSemanticVersion("1.2.3")).toEqual({
      major: 1,
      minor: 2,
      patch: 3,
      prerelease: [],
    });
    expect(parseSemanticVersion("1.2.3-beta.2+build.9").prerelease).toEqual([
      "beta",
      2,
    ]);
  });

  it("rejects leading zeroes and incomplete versions", () => {
    for (const value of ["1.2", "01.2.3", "1.02.3", "1.2.03", "v1.2.3"]) {
      expect(() => parseSemanticVersion(value)).toThrow();
    }
  });
});

describe("semantic version ordering", () => {
  it("orders core versions", () => {
    expect(compareSemanticVersions("0.4.2", "0.5.0")).toBeLessThan(0);
    expect(compareSemanticVersions("1.0.0", "0.99.99")).toBeGreaterThan(0);
    expect(compareSemanticVersions("1.2.3", "1.2.3+build.2")).toBe(0);
  });

  it("orders prerelease identifiers according to SemVer", () => {
    const ordered = [
      "1.0.0-alpha",
      "1.0.0-alpha.1",
      "1.0.0-alpha.beta",
      "1.0.0-beta",
      "1.0.0-beta.2",
      "1.0.0-beta.11",
      "1.0.0-rc.1",
      "1.0.0",
    ];
    for (let index = 0; index < ordered.length - 1; index += 1) {
      expect(
        compareSemanticVersions(ordered[index]!, ordered[index + 1]!),
      ).toBeLessThan(0);
    }
  });
});
