#!/usr/bin/env python3
"""Set the desktop release version in every release manifest."""

from __future__ import annotations

import re
import sys
from pathlib import Path

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
CARGO_VERSION_RE = re.compile(r'(?m)^(version = ")[^"]+(")')
NSH_JSON_VERSION_RE = re.compile(r'(?m)^(  "version": ")[^"]+(")')


def _replacement(path: Path, pattern: re.Pattern[str], version: str) -> tuple[Path, bytes]:
    text = path.read_bytes().decode("utf-8")
    if len(pattern.findall(text)) != 1:
        raise ValueError(f"{path}: expected exactly one release version")
    return path, pattern.sub(
        lambda match: f"{match.group(1)}{version}{match.group(2)}",
        text,
        count=1,
    ).encode("utf-8")


def set_version(root: Path, version: str) -> None:
    if VERSION_RE.fullmatch(version) is None:
        raise ValueError(f"release version must be MAJOR.MINOR.PATCH: {version}")

    paths = [(root / "Cargo.toml", CARGO_VERSION_RE)]
    bir_print = root / "crates/bir-print/Cargo.toml"
    if bir_print.exists():
        paths.append((bir_print, CARGO_VERSION_RE))
    paths.append((root / "nsh/nsh.json", NSH_JSON_VERSION_RE))

    updates = [_replacement(path, pattern, version) for path, pattern in paths]
    for path, content in updates:
        path.write_bytes(content)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: set_release_version.py MAJOR.MINOR.PATCH", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    try:
        set_version(root, argv[1])
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
