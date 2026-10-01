"""
assemble_handoff.py (ACAE)

Automates the mechanical half of the "run check_blueprint.py, open a
fresh AI-assistant session, copy-paste the sub-phase's prompt + files"
loop -- and only that half. This script never writes code, never edits
BACKEND_BLUEPRINT.md, never touches a backend/scrapers/frontend file.

Ported from the Nifty multi-strategy research platform's own
assemble_handoff.py. The parsing logic is unchanged -- ACAE's
BACKEND_BLUEPRINT.md Section 12 sub-phases are written in the same
Design-direction / Files-to-attach / **Prompt:** blockquote /
After-response-check shape Section 11's format template requires, so the
same regexes apply. The only real changes from the Nifty version are the
default stable tier (below) and the doc comments.

Note: ACAE's BACKEND_BLUEPRINT.md uses a plain "**Files to attach:** `a`, `b`"
line rather than Nifty's "Stage-Handoff" fenced code block, so
extract_files_to_attach() below always takes the fallback branch for
this project -- that's expected, not an error, and is why it's printed
as an info line rather than a warning here (unlike the Nifty version,
which treats it as a sign BACKEND_BLUEPRINT.md drifted from its own template).
"""
import ast
import json
import os
import re
import subprocess
import sys
import platform

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLUEPRINT_PATH = os.path.join(PROJECT_ROOT, "BACKEND_BLUEPRINT.md")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "handoff")
STABLE_TIER_PATH = os.path.join(PROJECT_ROOT, ".stable_tier.json")
DIGEST_PATH = os.path.join(PROJECT_ROOT, "digest.txt")

# Seeded from BACKEND_BLUEPRINT.md's own directory map (Section 9) -- files that
# rarely change once a phase closes, so future sub-phases can reference
# them by pointer instead of re-embedding full text every time.
DEFAULT_STABLE_TIER = [
    "BACKEND_BLUEPRINT.md",
    "backend/schema.sql",
    "backend/topic_taxonomy.json",
    "backend/cognitive_profiler.py",
    "backend/weak_point_selector.py",
    "backend/remedial_engine.py",
    "backend/db_helpers.py",
]

CHARS_PER_TOKEN_ESTIMATE = 4
TOKEN_WARN_THRESHOLD = 15_000


# --------------------------------------------------------------------------
# Stable-tier sidecar file
# --------------------------------------------------------------------------

def _load_stable_tier() -> set:
    if not os.path.isfile(STABLE_TIER_PATH):
        _save_stable_tier(set(DEFAULT_STABLE_TIER))
        console.print(Panel.fit(
            f"Created [bold cyan]{STABLE_TIER_PATH}[/bold cyan] seeded from BACKEND_BLUEPRINT.md's directory map "
            f"({len(DEFAULT_STABLE_TIER)} file(s)).\nEdit it, or use [bold green]--mark-stable/--unmark-stable[/bold green], "
            f"as more sub-phases close out.",
            title="[bold blue]Info[/bold blue]", border_style="blue"
        ))
        return set(DEFAULT_STABLE_TIER)
    try:
        with open(STABLE_TIER_PATH, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        console.print(Panel(
            f"[bold red]{STABLE_TIER_PATH}[/bold red] exists but couldn't be parsed as JSON.\n"
            f"Treating the stable tier as empty for this run.",
            title="[bold yellow]Warning[/bold yellow]", border_style="yellow"
        ))
        return set()


def _save_stable_tier(paths: set) -> None:
    with open(STABLE_TIER_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(paths), f, indent=2)
        f.write("\n")


def _handle_stable_tier_flags(argv: list) -> bool:
    stable = _load_stable_tier()

    if "--list-stable" in argv:
        table = Table(title=f"Stable Tier ({len(stable)} file(s))", border_style="cyan")
        table.add_column("File Path", style="cyan", no_wrap=True)
        table.add_column("Status", justify="left")

        for p in sorted(stable):
            exists = os.path.isfile(os.path.join(PROJECT_ROOT, p))
            status = "[green]On Disk[/green]" if exists else "[red]Missing on disk[/red]"
            table.add_row(p, status)

        console.print(table)
        return True

    if "--mark-stable" in argv:
        idx = argv.index("--mark-stable")
        new_paths = [a for a in argv[idx + 1:] if not a.startswith("--")]
        if not new_paths:
            console.print("[bold red]Usage:[/bold red] python scripts/assemble_handoff.py --mark-stable <path> [<path> ...]")
            return True
        stable |= set(new_paths)
        _save_stable_tier(stable)
        console.print(f"[bold green]✔ Marked stable ({len(new_paths)}):[/bold green] {', '.join(new_paths)}")
        console.print("[dim]These will no longer be embedded in full in future handoff blobs -- make sure they're actually uploaded to Claude Project knowledge.[/dim]")
        return True

    if "--unmark-stable" in argv:
        idx = argv.index("--unmark-stable")
        rm_paths = [a for a in argv[idx + 1:] if not a.startswith("--")]
        if not rm_paths:
            console.print("[bold red]Usage:[/bold red] python scripts/assemble_handoff.py --unmark-stable <path> [<path> ...]")
            return True
        stable -= set(rm_paths)
        _save_stable_tier(stable)
        console.print(f"[bold yellow]✔ Unmarked ({len(rm_paths)}):[/bold yellow] {', '.join(rm_paths)}")
        return True

    return False


# --------------------------------------------------------------------------
# check_blueprint.py / BACKEND_BLUEPRINT.md parsing
# --------------------------------------------------------------------------

def get_next_subphase_id() -> str:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    with console.status("[bold cyan]Querying check_blueprint.py...[/bold cyan]", spinner="dots"):
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "scripts", "check_blueprint.py")], cwd=PROJECT_ROOT, env=env,
            capture_output=True, encoding="utf-8", errors="replace", timeout=180,
        )

    match = re.search(r"NEXT UP.*?PHASE\s+(\S+)", result.stdout)
    if not match:
        console.print(Panel(
            "Couldn't find a 'NEXT UP -> PHASE ...' line in check_blueprint.py's output.\n\n"
            "Either every tracked sub-phase is done, check_blueprint.py errored, or 6.5/7 "
            "aren't the current phases anymore (check BACKEND_BLUEPRINT.md's Section 5).\n"
            "Pass the id explicitly: [bold cyan]`python scripts/assemble_handoff.py <id>`[/bold cyan].\n\n"
            f"[bold]Output:[/bold]\n{result.stdout}{result.stderr}",
            title="[bold red]Error: Auto-detect Failed[/bold red]", border_style="red"
        ))
        sys.exit(1)
    return match.group(1)


def find_subphase_section(blueprint_text: str, subphase_id: str):
    pattern = re.compile(
        rf"#### {re.escape(subphase_id)} — .*?(?=\n#### |\n---\n|\Z)",
        re.DOTALL,
    )
    m = pattern.search(blueprint_text)
    return m.group(0) if m else None


# Set by extract_prompt()/extract_files_to_attach() on the CURRENT
# sub-phase whenever they had to fall back to a looser-style parse.
# main() reads this right after calling both and prints one combined
# note. For ACAE, the "files" fallback fires on every sub-phase by
# design (see module docstring) -- expected, not a drift warning.
FALLBACK_USED = {"prompt": False, "files": False}


def extract_prompt(section_text: str):
    m = re.search(r"\*\*Prompt:\*\*\s*\n((?:>.*\n?)+)", section_text)
    if m:
        lines = [ln.lstrip(">").strip() for ln in m.group(1).splitlines()]
        return "\n".join(lines).strip()

    # Fallback for sub-phases written without an explicit **Prompt:**
    # blockquote: synthesize a working prompt from **Design direction:**
    # instead, clearly labeled as synthesized.
    m = re.search(
        r"\*\*Design direction:\*\*\s*(.*?)(?=\n\*\*Files to attach|\n\*\*After-response check|\Z)",
        section_text, re.DOTALL,
    )
    if not m:
        return None
    FALLBACK_USED["prompt"] = True
    design = " ".join(m.group(1).split())
    return (
        "(No **Prompt:** block in BACKEND_BLUEPRINT.md for this sub-phase -- "
        "synthesized from its **Design direction:** instead.)\n\n" + design
    )


def extract_files_to_attach(section_text: str):
    m = re.search(r"Stage-Handoff\s+([^\n`]*)", section_text)
    if not m:
        # ACAE's BACKEND_BLUEPRINT.md always takes this branch (see module
        # docstring) -- pull backtick-quoted paths out of the
        # "**Files to attach:** `a.py`, `b.py`" line.
        m2 = re.search(
            r"\*\*Files to attach:\*\*\s*(.*?)(?=\n\n|\n\*\*Prompt|\n\*\*After-response check|\Z)",
            section_text, re.DOTALL,
        )
        raw_files = re.findall(r"`([^`]+)`", m2.group(1)) if m2 else []
        if raw_files:
            FALLBACK_USED["files"] = True
    else:
        raw_files = m.group(1).strip().split(",")

    seen = set()
    out = []
    for f in raw_files:
        f = f.strip()
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def extract_after_response_check(section_text: str):
    m = re.search(r"\*\*After-response check:\*\*\s*(.*?)(?=\n\n|\Z)", section_text, re.DOTALL)
    return m.group(1).strip() if m else None


# --------------------------------------------------------------------------
# --lite docstring stripping
# --------------------------------------------------------------------------

def _strip_docstrings(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    lines = source.splitlines(keepends=True)
    targets = []

    def _check_body(body):
        if not body:
            return
        first = body[0]
        if (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            start = first.lineno
            end = getattr(first, "end_lineno", first.lineno)
            indent = " " * first.col_offset
            targets.append((start, end, indent))

    _check_body(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            _check_body(node.body)

    for start, end, indent in sorted(targets, key=lambda t: -t[0]):
        placeholder = f'{indent}"""(docstring omitted for --lite; see file on disk)"""\n'
        lines[start - 1:end] = [placeholder]

    return "".join(lines)


# --------------------------------------------------------------------------
# Blob assembly
# --------------------------------------------------------------------------

def build_blob(subphase_id: str, prompt, files: list, after_check,
               stable_tier: set, lite: bool, full: bool) -> tuple:
    parts = [
        f"=== Sub-phase {subphase_id} hand-off (ACAE) ===",
        "",
        prompt or (
            "(No **Prompt:** block found for this sub-phase in BACKEND_BLUEPRINT.md -- "
            "check that Section 11's formatting hasn't drifted from what "
            "extract_prompt() expects.)"
        ),
        "",
    ]
    per_file_stats = []

    for rel_path in files:
        full_path = os.path.join(PROJECT_ROOT, rel_path)
        is_stable = (rel_path in stable_tier) and not full

        if is_stable:
            pointer = (
                f"--- FILE: {rel_path} ---\n"
                f"(Assumed already in Claude Project knowledge -- not re-embedded. "
                f"Run with --full, or --unmark-stable {rel_path}, if it's actually "
                f"missing from project knowledge or you need to re-verify its content.)\n"
            )
            parts.append(pointer)
            per_file_stats.append((rel_path, len(pointer), False))
            continue

        parts.append(f"--- START FILE: {rel_path} ---")
        if os.path.isfile(full_path):
            with open(full_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
            if lite:
                content = _strip_docstrings(content)
            parts.append(content)
            per_file_stats.append((rel_path, len(content), True))
        else:
            missing_note = f"[MISSING ON DISK: {full_path}]"
            parts.append(missing_note)
            per_file_stats.append((rel_path, len(missing_note), True))
        parts.append(f"--- END FILE: {rel_path} ---")
        parts.append("")

    if after_check:
        parts.append("=== After-response check (run once you're done) ===")
        parts.append(after_check)

    return "\n".join(parts), per_file_stats


def _print_budget_summary(blob: str, per_file_stats: list) -> None:
    total_chars = len(blob)
    est_tokens = total_chars // CHARS_PER_TOKEN_ESTIMATE

    table = Table(title="Context Budget Estimate (~4 chars/token)", border_style="magenta")
    table.add_column("Tokens", justify="right", style="cyan", no_wrap=True)
    table.add_column("File Path", style="green")
    table.add_column("Status", justify="left")

    for rel_path, chars, embedded in sorted(per_file_stats, key=lambda t: -t[1]):
        tag = "[bold yellow]Embedded[/bold yellow]" if embedded else "[dim]Pointer only (Stable Tier)[/dim]"
        table.add_row(f"{chars // CHARS_PER_TOKEN_ESTIMATE:,}", rel_path, tag)

    console.print()
    console.print(table)
    console.print(f"[bold magenta]TOTAL:[/bold magenta] {est_tokens:,} tokens ({total_chars:,} chars)")

    if est_tokens > TOKEN_WARN_THRESHOLD:
        console.print(Panel(
            f"This blob is an estimated [bold red]{est_tokens:,}[/bold red] tokens, above the "
            f"{TOKEN_WARN_THRESHOLD:,}-token flag.\n\n"
            f"[bold]Consider:[/bold]\n"
            f"• Marking more finished-phase files stable ([cyan]--mark-stable[/cyan])\n"
            f"• Using [cyan]--lite[/cyan] for reference-only files\n"
            f"• Checking whether this sub-phase's Files-to-attach list in BACKEND_BLUEPRINT.md has grown too wide.",
            title="[bold yellow]Context Size Warning[/bold yellow]", border_style="red"
        ))


def _warn_if_digest_present() -> None:
    if os.path.isfile(DIGEST_PATH):
        console.print(Panel(
            f"[bold cyan]{DIGEST_PATH}[/bold cyan] exists in the project root.\n\n"
            f"If you're pasting this handoff blob into a chat, do [bold red]NOT[/bold red] also attach digest.txt "
            f"in the same conversation -- it duplicates the full text of most files this script already embeds. "
            f"[bold]Pick one or the other.[/bold]",
            title="[bold yellow]Warning: digest.txt Detected[/bold yellow]", border_style="yellow"
        ))


def open_directory(path: str) -> None:
    """Opens the specified directory in the OS file explorer."""
    if not os.path.exists(path):
        return

    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", path])
        else:  # Linux/Unix
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        console.print(f"[dim yellow]Could not automatically open folder: {e}[/dim yellow]")


def main():
    argv = sys.argv[1:]

    if _handle_stable_tier_flags(argv):
        return

    positional = [a for a in argv if not a.startswith("--")]
    want_clipboard = "--clipboard" in argv
    want_lite = "--lite" in argv
    want_full = "--full" in argv

    subphase_id = positional[0] if positional else get_next_subphase_id()

    if not os.path.isfile(BLUEPRINT_PATH):
        console.print(f"[bold red]Error:[/bold red] BACKEND_BLUEPRINT.md not found at {BLUEPRINT_PATH}")
        sys.exit(1)

    with open(BLUEPRINT_PATH, encoding="utf-8") as f:
        blueprint_text = f.read()

    section = find_subphase_section(blueprint_text, subphase_id)
    if section is None:
        console.print(Panel(
            f"Couldn't find a '#### {subphase_id} — ...' section in BACKEND_BLUEPRINT.md.\n"
            f"Either the id is wrong, or this sub-phase has already been collapsed into a recap row (which means it's already done).",
            title="[bold red]Section Not Found[/bold red]", border_style="red"
        ))
        sys.exit(1)

    FALLBACK_USED["prompt"] = False  # reset per-run; these two functions set them as a side effect
    FALLBACK_USED["files"] = False
    prompt = extract_prompt(section)
    files = extract_files_to_attach(section)
    after_check = extract_after_response_check(section)
    stable_tier = _load_stable_tier()

    if not files:
        console.print(f"[yellow]Warning:[/yellow] No 'Files to attach' list found for {subphase_id} -- writing the prompt only.")
    if not prompt:
        console.print(f"[yellow]Warning:[/yellow] No '**Prompt:**' block found for {subphase_id} -- double-check BACKEND_BLUEPRINT.md formatting.")

    if FALLBACK_USED["prompt"]:
        console.print(Panel(
            f"Sub-phase {subphase_id} has no **Prompt:** blockquote in BACKEND_BLUEPRINT.md -- "
            f"the prompt for this hand-off was [bold]synthesized from Design direction[/bold] instead.\n\n"
            f"This still produced a usable hand-off, but it's worth rewriting {subphase_id}'s "
            f"BACKEND_BLUEPRINT.md entry into the standard format (Section 11) at some point -- a synthesized "
            f"prompt is looser and more prone to dangling references than one actually written "
            f"for a fresh chat with no prior context.",
            title="[bold yellow]Fallback parsing used: prompt[/bold yellow]", border_style="yellow",
        ))
    if FALLBACK_USED["files"]:
        console.print(
            "[dim]Note: files list parsed from a plain 'Files to attach:' line (expected for "
            "ACAE's BACKEND_BLUEPRINT.md -- it doesn't use Nifty's Stage-Handoff code-block style).[/dim]"
        )

    with console.status(f"[bold green]Building blob for sub-phase {subphase_id}...[/bold green]", spinner="arc"):
        blob, per_file_stats = build_blob(
            subphase_id, prompt, files, after_check, stable_tier, lite=want_lite, full=want_full
        )

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out_path = os.path.join(OUTPUT_DIR, f"{subphase_id}_handoff.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(blob)

    n_embedded = sum(1 for _, _, embedded in per_file_stats if embedded)
    n_pointer = len(per_file_stats) - n_embedded

    status_msg = (f"[bold green]✔ Wrote[/bold green] [bold cyan]{out_path}[/bold cyan]  "
                  f"({n_embedded} file(s) embedded")
    status_msg += f", {n_pointer} pointed at project knowledge" if n_pointer else ""
    status_msg += f", [green]prompt found[/green])" if prompt else ", [red]NO PROMPT FOUND[/red])"

    console.print(status_msg)

    _print_budget_summary(blob, per_file_stats)
    _warn_if_digest_present()

    if want_clipboard:
        try:
            import pyperclip
            pyperclip.copy(blob)
            console.print("\n[bold green]✔ Copied hand-off blob to clipboard.[/bold green]")
        except ImportError:
            console.print(Panel(
                "[bold cyan]pyperclip[/bold cyan] not installed.\n"
                "Run: [green]pip install pyperclip[/green]\n"
                "(The .txt file still has everything; paste from that instead)",
                title="[yellow]Clipboard Failed[/yellow]", border_style="yellow"
            ))

    open_directory(OUTPUT_DIR)


if __name__ == "__main__":
    main()
