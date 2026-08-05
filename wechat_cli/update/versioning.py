"""Strict Semantic Versioning parsing and precedence helpers."""

from __future__ import annotations

import re
from functools import total_ordering
from typing import Iterable


_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

PrereleasePart = int | str


def _parse_prerelease(value: str | None) -> tuple[PrereleasePart, ...]:
    if value is None:
        return ()
    parts: list[PrereleasePart] = []
    for identifier in value.split("."):
        if identifier.isdigit():
            if len(identifier) > 1 and identifier.startswith("0"):
                raise ValueError("numeric prerelease identifiers cannot contain leading zeroes")
            parts.append(int(identifier))
        else:
            parts.append(identifier)
    return tuple(parts)


def _parse_build(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(value.split("."))


@total_ordering
class SemanticVersion:
    """A strict SemVer value whose equality ignores build metadata."""

    __slots__ = ("major", "minor", "patch", "prerelease", "build")

    def __init__(
        self,
        major: int,
        minor: int,
        patch: int,
        prerelease: Iterable[PrereleasePart] = (),
        build: Iterable[str] = (),
    ) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = tuple(prerelease)
        self.build = tuple(build)

    @classmethod
    def parse(cls, value: str) -> "SemanticVersion":
        if not isinstance(value, str):
            raise ValueError("version must be a string")
        match = _SEMVER_RE.fullmatch(value)
        if match is None:
            raise ValueError(f"invalid semantic version: {value!r}")
        major, minor, patch, prerelease, build = match.groups()
        return cls(
            int(major),
            int(minor),
            int(patch),
            _parse_prerelease(prerelease),
            _parse_build(build),
        )

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            value += "-" + ".".join(str(part) for part in self.prerelease)
        if self.build:
            value += "+" + ".".join(self.build)
        return value

    def __repr__(self) -> str:
        return f"SemanticVersion({str(self)!r})"

    def _core(self) -> tuple[int, int, int]:
        return self.major, self.minor, self.patch

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return self._core() == other._core() and self.prerelease == other.prerelease

    def __hash__(self) -> int:
        return hash((self._core(), self.prerelease))

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        if self._core() != other._core():
            return self._core() < other._core()
        if not self.prerelease:
            return False
        if not other.prerelease:
            return True
        for left, right in zip(self.prerelease, other.prerelease):
            if left == right:
                continue
            if isinstance(left, int) and isinstance(right, str):
                return True
            if isinstance(left, str) and isinstance(right, int):
                return False
            return left < right
        return len(self.prerelease) < len(other.prerelease)


def is_newer_version(candidate: str, current: str) -> bool:
    return SemanticVersion.parse(candidate) > SemanticVersion.parse(current)
