#!/usr/bin/env python3
"""Report public Python defs missing docstrings (code-docs standard).

Usage (repo root):
  python scripts/research/docstring_coverage_report.py
  python scripts/research/docstring_coverage_report.py --limit 30
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ROOTS = [
    ROOT / "packages" / "py" / "analytics" / "src",
    ROOT / "packages" / "py" / "application" / "src",
    ROOT / "packages" / "py" / "domain" / "src",
    ROOT / "packages" / "py" / "infrastructure" / "src",
    ROOT / "packages" / "py" / "market" / "src",
    ROOT / "apps" / "api-python" / "src" / "bolsa_api",
]


def _public_defs(path: Path) -> list[tuple[int, str, str, bool]]:
    """Return (lineno, kind, name, has_doc) for public top-level classes/functions."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    out: list[tuple[int, str, str, bool]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            out.append((node.lineno, "Class", node.name, bool(ast.get_docstring(node))))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            out.append((node.lineno, kind, node.name, bool(ast.get_docstring(node))))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Docstring coverage report")
    p.add_argument("--limit", type=int, default=40, help="Max missing samples to print")
    args = p.parse_args()

    total = 0
    missing = 0
    samples: list[str] = []
    modules_missing = 0
    modules_total = 0

    for root in DEFAULT_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if path.name.startswith("test_"):
                continue
            modules_total += 1
            try:
                mod = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            if not ast.get_docstring(mod):
                modules_missing += 1
            for lineno, kind, name, has_doc in _public_defs(path):
                total += 1
                if not has_doc:
                    missing += 1
                    if len(samples) < args.limit:
                        rel = path.relative_to(ROOT).as_posix()
                        samples.append(f"{rel}:{lineno} {kind} {name}")

    pct = (100.0 * missing / total) if total else 0.0
    print("=== docstring coverage (public defs) ===")
    print(f"defs_total={total} missing={missing} pct_missing={pct:.1f}%")
    print(f"modules_total={modules_total} modules_without_doc={modules_missing}")
    print("\nSamples (missing):")
    for line in samples:
        print(f"  {line}")
    print(
        "\nPolicy: docs/engineering/code-documentation-standard-2026-08-03.md",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
