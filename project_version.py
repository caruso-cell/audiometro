"""Utilities for reading and comparing the project semantic version."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Tuple

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)
_VERSION_FILENAME = "VERSION"


def _candidate_paths() -> list[Path]:
    """Return possible locations of the VERSION file."""
    base_dir = Path(__file__).resolve().parent
    candidates = [base_dir / _VERSION_FILENAME]
    runtime_dir = Path(getattr(sys, "_MEIPASS", base_dir))
    if runtime_dir not in candidates:
        candidates.append(runtime_dir / _VERSION_FILENAME)
    return candidates


def read_version() -> str:
    """Read the semantic version string, falling back to 0.0.0 when missing."""
    for path in _candidate_paths():
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not raw:
            continue
        if not _SEMVER_RE.fullmatch(raw):
            raise ValueError(f"Invalid semantic version: {raw!r}")
        return raw
    return "0.0.0"


def write_version(version: str) -> Path:
    """Persist a validated semantic version to the repository copy of VERSION."""
    if not _SEMVER_RE.fullmatch(version):
        raise ValueError(f"Invalid semantic version: {version!r}")
    target = Path(__file__).resolve().parent / _VERSION_FILENAME
    target.write_text(version + "\n", encoding="utf-8")
    return target


def parse_semver(version: str) -> Tuple[int, int, int, Tuple[object, ...]]:
    """Parse a semantic version into a tuple suitable for comparisons."""
    match = _SEMVER_RE.fullmatch(version)
    if not match:
        raise ValueError(f"Invalid semantic version: {version!r}")
    major, minor, patch, prerelease, _build = match.groups()
    pre_tokens: list[object] = []
    if prerelease:
        for token in prerelease.split('.'):
            if token.isdigit():
                pre_tokens.append(int(token))
            else:
                pre_tokens.append(token.lower())
    return int(major), int(minor), int(patch), tuple(pre_tokens)


def compare_versions(first: str, second: str) -> int:
    """Return 1 if first>second, -1 if first<second, 0 if equal."""
    a_major, a_minor, a_patch, a_pre = parse_semver(first)
    b_major, b_minor, b_patch, b_pre = parse_semver(second)

    if a_major != b_major:
        return 1 if a_major > b_major else -1
    if a_minor != b_minor:
        return 1 if a_minor > b_minor else -1
    if a_patch != b_patch:
        return 1 if a_patch > b_patch else -1

    if a_pre == b_pre:
        return 0
    if not a_pre:
        return 1
    if not b_pre:
        return -1

    for left, right in zip(a_pre, b_pre):
        if left == right:
            continue
        if isinstance(left, int) and isinstance(right, int):
            return 1 if left > right else -1
        if isinstance(left, int) and isinstance(right, str):
            return -1
        if isinstance(left, str) and isinstance(right, int):
            return 1
        return 1 if str(left) > str(right) else -1

    if len(a_pre) != len(b_pre):
        return 1 if len(a_pre) > len(b_pre) else -1
    return 0


try:
    __version__ = read_version()
except ValueError:
    __version__ = "0.0.0"

__all__ = [
    "__version__",
    "read_version",
    "write_version",
    "parse_semver",
    "compare_versions",
]
