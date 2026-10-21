# SPDX-License-Identifier: MIT
# Copyright (c) 2026 John (ASD-max)
"""Read-only verification of human-declared rule blocks; Python standard library only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

__version__ = "0.2.0"

TEXT_SUFFIXES = {".md", ".txt"}


def inside(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("Candidate paths must be nonempty relative paths")
    try:
        path = (root / name).resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Cannot resolve candidate path: {name}") from exc
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Candidate path escapes root: {name}")
    return path


def check(source: Path, candidate: Path, spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ValueError("Inventory must be a JSON object")
    if not source.is_file():
        raise ValueError("Source must be an existing regular UTF-8 file")
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError("Candidate must be an existing non-symlink directory")
    raw = source.read_bytes()
    raw.decode("utf-8")
    lines = raw.splitlines(keepends=True)
    digest = spec.get("source_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("source_sha256 must be a lowercase SHA-256 hex digest")
    if digest != hashlib.sha256(raw).hexdigest():
        raise ValueError("Source hash does not match reviewed inventory")
    core, blocks = spec.get("core_files"), spec.get("blocks")
    if not isinstance(core, list) or not core or not isinstance(blocks, list) or not blocks:
        raise ValueError("Nonempty core_files and blocks are required")
    core_paths = [inside(candidate, name) for name in core]
    if len(set(core_paths)) != len(core_paths):
        raise ValueError("Duplicate core file")
    for path in core_paths:
        if path.suffix not in TEXT_SUFFIXES or not path.is_file():
            raise ValueError("Core files must be existing .md or .txt files")

    documents = {}

    def fail_walk(error: OSError) -> None:
        raise error

    for directory, dirs, files in os.walk(candidate, onerror=fail_walk, followlinks=False):
        for name in dirs + files:
            if (Path(directory) / name).is_symlink():
                raise ValueError("Candidate tree contains a symlink; use a self-contained copy")
        for name in files:
            path = Path(directory) / name
            if path.suffix not in TEXT_SUFFIXES or not path.is_file():
                raise ValueError("Candidate must contain only regular UTF-8 .md and .txt files")
            relative = str(path.relative_to(candidate))
            data = inside(candidate, relative).read_bytes()
            data.decode("utf-8")
            documents[relative] = data.splitlines(keepends=True)

    results, seen = [], set()
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError("Each block must be an object")
        ident, start, end = block.get("id"), block.get("start"), block.get("end")
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise ValueError("Block IDs must be nonempty and unique")
        ident.encode("utf-8")
        seen.add(ident)
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise ValueError(f"Invalid source range: {ident}")
        block_lines = lines[start - 1:end]
        content = b"".join(block_lines)
        if not content.strip():
            raise ValueError(f"Empty source block: {ident}")
        occurrences = {}
        for name, data in documents.items():
            count = sum(data[i:i + len(block_lines)] == block_lines
                        for i in range(len(data) - len(block_lines) + 1))
            if count:
                occurrences[name] = count
        in_core = any(inside(candidate, name) in core_paths for name in occurrences)
        results.append({"id": ident, "pass": sum(occurrences.values()) == 1 and in_core,
                        "source_lines": [start, end], "occurrences": occurrences,
                        "in_declared_core": in_core,
                        "sha256": hashlib.sha256(content).hexdigest()})
    return {"pass": all(row["pass"] for row in results), "blocks": results,
            "limits": "Checks declared blocks only. Manually verify inventory completeness and unconditional entry routing; use model read traces for actual loading."}

class InputError(ValueError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError(message)


def parser() -> Parser:
    result = Parser(prog="rule-preserve", description="Check declared source blocks in an isolated candidate tree.")
    result.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = result.add_subparsers(dest="command", required=True, parser_class=Parser)
    verify = commands.add_parser("check", help="Verify byte-exact preservation of reviewed blocks")
    verify.add_argument("source", type=Path)
    verify.add_argument("candidate", type=Path)
    verify.add_argument("spec", type=Path)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = list(sys.argv[1:] if argv is None else argv)
    command = "check" if arguments and arguments[0] == "check" else None
    try:
        args = parser().parse_args(arguments)
        command = args.command
        if not args.spec.is_file():
            raise InputError("Inventory must be an existing regular UTF-8 JSON file")
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        result = check(args.source, args.candidate, spec)
        code = 0 if result["pass"] else 1
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        result = {"pass": False, "error": str(exc)}
        code = 2
    json.dump({"schema_version": 1, "command": command, **result}, sys.stdout,
              ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
