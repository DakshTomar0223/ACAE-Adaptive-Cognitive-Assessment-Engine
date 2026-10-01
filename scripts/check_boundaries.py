"""Backend layer-boundary check for ACAE (stdlib only).

Enforces the import rules in ACAE_ARCHITECTURE.md section 4 by parsing every
.py file under backend/ with `ast` (no code is executed). It is the ACAE
counterpart of Nifty's "engine stays dumb on purpose" rule, made mechanical.

    python scripts/check_boundaries.py            # exit 0 = clean, 1 = violations
    python scripts/check_boundaries.py --root path/to/backend

Rules, per top-level package under backend/:
  * internal imports may only target the packages listed in ALLOWED_INTERNAL
  * third-party imports in FORBIDDEN_EXTERNAL[layer] are rejected
  * a top-level package that is not classified in ALLOWED_INTERNAL is itself a
    violation, so a new folder cannot silently dodge the rules

tests/ and scripts/ directories are skipped (they may import anything).
The default root is anchored to __file__, never to the current directory.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# layer -> internal layers it may import (itself is always allowed)
ALLOWED_INTERNAL: dict[str, set[str]] = {
    "domain":        set(),
    "data_platform": {"domain"},
    "engine":        {"domain"},
    "services":      {"domain", "engine", "data_platform"},
    "api":           {"domain", "services"},
    "tagging":       {"domain"},
    "scrapers":      {"domain", "data_platform", "tagging"},
}

_WEB = {"flask", "fastapi", "starlette", "uvicorn", "flask_cors"}
_IO = {"sqlite3", "requests", "httpx", "anthropic", "playwright", "pytesseract", "pdfplumber"}

# layer -> third-party/stdlib top-level modules it must NOT import
FORBIDDEN_EXTERNAL: dict[str, set[str]] = {
    "domain":        _WEB | _IO,
    "data_platform": _WEB | {"requests", "httpx", "anthropic", "playwright"},
    "engine":        _WEB | _IO,
    "services":      _WEB | {"sqlite3", "requests", "httpx", "anthropic", "playwright"},
    "api":           {"sqlite3", "requests", "httpx", "anthropic", "playwright"},
    "tagging":       _WEB | {"sqlite3"},
    "scrapers":      _WEB,
}

SKIP_DIRS = {"tests", "scripts", "__pycache__", "node_modules", ".venv", "venv"}


def _py_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        yield path, rel


def _imports(tree: ast.AST, rel: Path):
    """Yield (lineno, top_level_module) for every import in the file.

    Relative imports are resolved against the file's own package; a relative
    import that stays inside the same top-level package yields that package.
    """
    pkg_parts = list(rel.parts[:-1])  # e.g. ["engine", "detectors"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative
                base = pkg_parts[: max(len(pkg_parts) - (node.level - 1), 0)]
                target = base + (node.module.split(".") if node.module else [])
                yield node.lineno, (target[0] if target else (pkg_parts[0] if pkg_parts else ""))
            elif node.module:
                yield node.lineno, node.module.split(".")[0]


def check(root: Path) -> list[str]:
    violations: list[str] = []
    for path, rel in _py_files(root):
        if len(rel.parts) == 1:          # loose file at backend/ root (e.g. __init__)
            continue
        layer = rel.parts[0]
        if layer not in ALLOWED_INTERNAL:
            violations.append(f"{rel}: top-level package '{layer}' is not classified in "
                              f"ALLOWED_INTERNAL (add it deliberately or move the file)")
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            violations.append(f"{rel}: cannot parse ({exc.msg}, line {exc.lineno})")
            continue
        for lineno, mod in _imports(tree, rel):
            if mod in ALLOWED_INTERNAL and mod != layer:
                if mod not in ALLOWED_INTERNAL[layer]:
                    violations.append(f"{rel}:{lineno}: layer '{layer}' may not import layer '{mod}'")
            elif mod == "frontend":
                violations.append(f"{rel}:{lineno}: backend must never import from frontend/")
            elif mod in FORBIDDEN_EXTERNAL[layer]:
                violations.append(f"{rel}:{lineno}: layer '{layer}' may not import '{mod}'")
    return violations


def main(argv: list[str] | None = None) -> int:
    default_root = Path(__file__).resolve().parent.parent / "backend"
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root)
    args = ap.parse_args(argv)
    if not args.root.is_dir():
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 2
    found = check(args.root)
    if found:
        print(f"{len(found)} boundary violation(s):")
        for line in found:
            print("  " + line)
        return 1
    print("boundaries OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
