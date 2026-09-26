"""
check_blueprint.py (ACAE)

Checks the actual repo state against BLUEPRINT.md's current Phase 6.5/7
lettered sub-phases, tells you which one to work on next, and (with
--apply) syncs BLUEPRINT.md's Section 5 status-table rows for "6.5" and
"7" to match reality.

Ported from the Nifty multi-strategy research platform's own
check_blueprint.py, scoped down to ACAE's directory layout and phases.
Deliberately simpler than the Nifty version in two ways, both by design
rather than oversight:

1. No git auto-commit. ACAE's sessions are typically shorter and more
   frontend-heavy; add it yourself if you want it (see _git_commit_phases
   in the Nifty version for the pattern).
2. Most sub-phases here are checked by "does the expected output file
   exist" rather than "does this function have the right signature" --
   Phase 7's sub-phases each produce one or two new files
   (scrapers/base_scraper.py, scrapers/parsing.py, ...), so file
   existence is a faithful proxy for "was this sub-phase actually done."
   6H is the one sub-phase in this document that is NOT file-existence
   checkable -- typography/contrast/dropdown-theming quality needs an
   actual contrast tool and a human's eyes, not a script. 6H is only
   ever marked done via `--signoff 6H`, recorded in a local sidecar file
   -- never inferred from file contents. This is intentional, not a gap
   to "fix" by trying to regex-detect good typography.

Run from the project root (same convention as Nifty's project):
    python check_blueprint.py               # report only, no file changes
    python check_blueprint.py --apply       # also sync BLUEPRINT.md's status table
    python check_blueprint.py --signoff 6H  # record a manually-verified sub-phase
"""

import json
import os
import re
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BLUEPRINT_PATH = os.path.join(PROJECT_ROOT, "BLUEPRINT.md")
SIGNOFF_PATH = os.path.join(PROJECT_ROOT, ".phase_signoff.json")


# --------------------------------------------------------------------------
# Manual sign-off sidecar (for sub-phases no script can verify, e.g. 6H)
# --------------------------------------------------------------------------

def _load_signoffs() -> set:
    if not os.path.isfile(SIGNOFF_PATH):
        return set()
    try:
        with open(SIGNOFF_PATH, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        console.print(Panel(
            f"[bold red]{SIGNOFF_PATH}[/bold red] exists but couldn't be parsed as JSON. "
            f"Treating sign-offs as empty for this run.",
            title="[bold yellow]Warning[/bold yellow]", border_style="yellow",
        ))
        return set()


def _save_signoffs(ids: set) -> None:
    with open(SIGNOFF_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2)
        f.write("\n")


def _handle_signoff_flag(argv: list) -> bool:
    if "--signoff" not in argv:
        return False
    idx = argv.index("--signoff")
    ids = [a for a in argv[idx + 1:] if not a.startswith("--")]
    if not ids:
        console.print("[bold red]Usage:[/bold red] python check_blueprint.py --signoff <id> [<id> ...]")
        return True
    signed = _load_signoffs()
    signed |= set(ids)
    _save_signoffs(signed)
    console.print(f"[bold green]✔ Recorded manual sign-off ({len(ids)}):[/bold green] {', '.join(ids)}")
    console.print(
        "[dim]Only sign off a sub-phase after you've actually worked through its "
        "after-response checklist in BLUEPRINT.md -- this file is trusted at face value.[/dim]"
    )
    return True


# --------------------------------------------------------------------------
# Check primitives
# --------------------------------------------------------------------------

def file_exists(rel_path: str):
    def _check():
        ok = os.path.exists(os.path.join(PROJECT_ROOT, rel_path))
        return ok, f"{rel_path} {'exists' if ok else 'missing'}"
    _check.label = rel_path
    return _check


def files_exist(rel_paths: list):
    def _check():
        missing = [p for p in rel_paths if not os.path.exists(os.path.join(PROJECT_ROOT, p))]
        ok = not missing
        detail = "all present" if ok else f"missing: {', '.join(missing)}"
        return ok, detail
    _check.label = f"{len(rel_paths)} file(s)"
    return _check


def content_contains(rel_path: str, substrings: list):
    def _check():
        full = os.path.join(PROJECT_ROOT, rel_path)
        if not os.path.isfile(full):
            return False, f"{rel_path} missing"
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read()
        missing = [s for s in substrings if s not in text]
        ok = not missing
        detail = "all markers present" if ok else f"missing markers: {', '.join(missing)}"
        return ok, detail
    _check.label = f"{rel_path} content"
    return _check


def manual_signoff(sub_id: str):
    def _check():
        signed = _load_signoffs()
        ok = sub_id in signed
        detail = "manually signed off" if ok else f"not yet signed off -- run: python check_blueprint.py --signoff {sub_id}"
        return ok, detail
    _check.label = "manual sign-off"
    return _check


# --------------------------------------------------------------------------
# Phase registry
# --------------------------------------------------------------------------
# Each entry: (id, short name, [check_fn, ...]). A sub-phase is "done" only
# when every one of its checks passes. Order here is the order BLUEPRINT.md
# presents them in, which is also the order "NEXT UP" walks through.

PHASES = [
    ("6E", "Theme tokens + shared shell", [
        files_exist([
            "frontend/app/globals.css",
            "frontend/app/layout.tsx",
            "frontend/app/components/Header.tsx",
            "frontend/app/components/ThemeToggle.tsx",
            "frontend/app/icon.svg",
        ]),
    ]),
    ("6F", "Quiz screen redesign", [
        files_exist(["frontend/app/page.tsx", "frontend/app/page.module.css"]),
    ]),
    ("6G", "Results screen redesign", [
        files_exist(["frontend/app/results/page.tsx", "frontend/app/results/results.module.css"]),
    ]),
    ("6H0", "Isolation audit tooling", [
        file_exists("scripts/audit_frontend_integration.py"),
        content_contains("scripts/audit_frontend_integration.py", ["--snapshot", "--check"]),
    ]),
    ("6H", "Fix pass: typography, contrast, dropdown theming", [
        manual_signoff("6H"),
    ]),
    ("7A", "PYQ source survey", [
        file_exists("scrapers/SOURCE_SURVEY.md"),
    ]),
    ("7B", "Archive schema design", [
        files_exist(["scrapers/ARCHIVE_SCHEMA.md", "scrapers/raw_record.py"]),
    ]),
    ("7C", "Scraper framework", [
        file_exists("scrapers/base_scraper.py"),
        file_exists("scrapers/sources"),
    ]),
    ("7D", "Parsing, normalization and dedup", [
        file_exists("scrapers/parsing.py"),
    ]),
    ("7E", "Tagging and human review queue", [
        file_exists("scrapers/tag_and_review.py"),
    ]),
    ("7F", "Bulk validation and load into questions", [
        file_exists("scrapers/load_archive.py"),
    ]),
    ("7G", "Coverage validation", [
        file_exists("scrapers/check_coverage.py"),
    ]),
]

# Which top-level phase (as it appears in Section 5's status table) each
# sub-phase id rolls up into, so --apply can sync that phase's status cell.
TOP_LEVEL_PHASE = {
    "6E": "6.5", "6F": "6.5", "6G": "6.5", "6H0": "6.5", "6H": "6.5",
    "7A": "7", "7B": "7", "7C": "7", "7D": "7", "7E": "7", "7F": "7", "7G": "7",
}


def run_all_checks():
    """Returns {sub_id: [(ok, detail), ...]} for every sub-phase above."""
    results = {}
    for sub_id, _name, checks in PHASES:
        results[sub_id] = [check() for check in checks]
    return results


def sub_phase_status(check_results: list) -> bool:
    return all(ok for ok, _detail in check_results)


def top_level_status(sub_ids: list, results: dict) -> str:
    statuses = [sub_phase_status(results[sid]) for sid in sub_ids]
    if all(statuses):
        return "done"
    if any(statuses):
        return "in progress"
    return "not started"


# --------------------------------------------------------------------------
# BLUEPRINT.md status-table sync (--apply)
# --------------------------------------------------------------------------

STATUS_LABEL = {
    "done": "Done",
    "in progress": "In progress",
    "not started": "Not started",
}


def sync_status_table(blueprint_text: str, all_results: dict) -> str:
    """Rewrites Section 5's status-table cell for phase 6.5 and phase 7
    to match the aggregate status computed from PHASES/TOP_LEVEL_PHASE.
    Only touches the status column of those two rows; leaves everything
    else (including phase 8's roadmap-only row) untouched."""
    updated = blueprint_text

    for phase_num in ("6.5", "7"):
        sub_ids = [sid for sid, top in TOP_LEVEL_PHASE.items() if top == phase_num]
        status = top_level_status(sub_ids, all_results)
        label = STATUS_LABEL[status]

        # Matches a Section-5 table row starting with "| **6.5** |" or
        # "| **7** |" through to the end of that row (next "|\n").
        row_re = re.compile(
            rf"(\|\s*\*\*{re.escape(phase_num)}\*\*\s*\|[^\n]*?\|)[^\n]*(\|\s*\n)"
        )
        m = row_re.search(updated)
        if not m:
            continue
        new_row = f"{m.group(1)} {label}{m.group(2)}"
        updated = updated[: m.start()] + new_row + updated[m.end():]

    return updated


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def print_report(all_results: dict):
    table = Table(title="ACAE — BLUEPRINT.md sub-phase status", border_style="cyan")
    table.add_column("ID", style="bold cyan", no_wrap=True)
    table.add_column("Sub-phase", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="dim")

    for sub_id, name, _checks in PHASES:
        results = all_results[sub_id]
        done = sub_phase_status(results)
        status = "[bold green]DONE[/bold green]" if done else "[bold yellow]TODO[/bold yellow]"
        detail = "; ".join(d for _ok, d in results)
        table.add_row(sub_id, name, status, detail)

    console.print(table)

    next_id = None
    for sub_id, _name, _checks in PHASES:
        if not sub_phase_status(all_results[sub_id]):
            next_id = sub_id
            break

    if next_id:
        console.print(f"\n[bold magenta]NEXT UP -> PHASE {next_id}[/bold magenta]")
    else:
        console.print("\n[bold green]All tracked sub-phases (6.5 and 7) are done![/bold green]")


def main():
    argv = sys.argv[1:]

    if _handle_signoff_flag(argv):
        return

    if not os.path.isfile(BLUEPRINT_PATH):
        console.print(f"[bold red]Error:[/bold red] BLUEPRINT.md not found at {BLUEPRINT_PATH}")
        sys.exit(1)

    all_results = run_all_checks()
    print_report(all_results)

    if "--apply" in argv:
        with open(BLUEPRINT_PATH, encoding="utf-8") as f:
            blueprint_text = f.read()
        updated = sync_status_table(blueprint_text, all_results)
        if updated != blueprint_text:
            with open(BLUEPRINT_PATH, "w", encoding="utf-8") as f:
                f.write(updated)
            console.print(f"\n[bold green]Updated {BLUEPRINT_PATH}'s Section 5 status table.[/bold green]")
        else:
            console.print("\n[dim]BLUEPRINT.md's status table already matches current results -- no changes made.[/dim]")


if __name__ == "__main__":
    main()
