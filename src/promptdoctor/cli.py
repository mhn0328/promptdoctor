"""Command line interface for promptdoctor."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .report import render_github, render_json, render_rule_list, render_text, summarize
from .rules import RULES, LintResult, lint

PROMPT_SUFFIXES = (".md", ".txt", ".prompt", ".tmpl", ".j2", ".jinja")

SKIP_DIRS = {".git", ".hg", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache"}

EPILOG = """examples:
  promptdoctor prompts/                 # lint every .md/.txt prompt in a folder
  promptdoctor system.prompt -           # two prompts: a file and stdin
  cat prompt.txt | promptdoctor --format json
  promptdoctor prompts/ --strict        # treat warnings as failures in CI
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptdoctor",
        description="A tiny static linter for LLM prompts.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="PATH",
        help="prompt files or directories to lint; use - for stdin (default: stdin when piped)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "github"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2000,
        metavar="N",
        help="warn when a prompt exceeds N estimated tokens (default: 2000)",
    )
    parser.add_argument(
        "--disable",
        action="append",
        default=[],
        metavar="IDS",
        help="comma-separated rule ids to skip, e.g. --disable PD101,PD108",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero on warnings too",
    )
    parser.add_argument("--list-rules", action="store_true", help="print the rule table and exit")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="text mode only: print just the exit code (json/github stay parseable)",
    )
    parser.add_argument("--version", action="version", version=f"promptdoctor {__version__}")
    return parser


def _iter_prompt_files(root: Path) -> List[Path]:
    found: List[Path] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            path = Path(current) / name
            if name.lower().endswith(PROMPT_SUFFIXES):
                found.append(path)
    return found


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _lint_file(path: Path, max_tokens: int, disable: Sequence[str]) -> LintResult:
    try:
        text = _read(path)
    except OSError as exc:  # pragma: no cover - depends on filesystem
        print(f"promptdoctor: {path}: {exc}", file=sys.stderr)
        text = ""
    return lint(text, str(path), max_tokens=max_tokens, disable=disable)


def _resolve_targets(
    paths: Sequence[str],
    stdin_text: Optional[str],
    *,
    max_tokens: int,
    disable: Sequence[str],
) -> List[LintResult]:
    """Turn CLI paths into lint results, reading stdin when needed."""
    if not paths:
        if stdin_text is None:
            return []
        return [lint(stdin_text, "<stdin>", max_tokens=max_tokens, disable=disable)]

    results: List[LintResult] = []
    for raw in paths:
        if raw == "-":
            if stdin_text is None:
                print("promptdoctor: '-' given but stdin is empty", file=sys.stderr)
                continue
            results.append(lint(stdin_text, "<stdin>", max_tokens=max_tokens, disable=disable))
            continue

        path = Path(raw)
        if path.is_dir():
            files = _iter_prompt_files(path)
            if not files:
                print(f"promptdoctor: no prompt files under {raw}", file=sys.stderr)
            for file_path in files:
                results.append(_lint_file(file_path, max_tokens, disable))
        elif path.is_file():
            results.append(_lint_file(path, max_tokens, disable))
        else:
            print(f"promptdoctor: cannot read {raw}", file=sys.stderr)

    return results


def _use_color(requested_off: bool, stream) -> bool:
    if requested_off or os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_rules:
        print(render_rule_list(RULES))
        return 0

    max_tokens = max(1, args.max_tokens)
    disable = [item for chunk in args.disable for item in chunk.split(",") if item.strip()]

    unknown = sorted({d.strip().upper() for d in disable} - {rule.id for rule in RULES})
    if unknown:
        parser.error("unknown rule id(s): " + ", ".join(unknown))

    stdin_text: Optional[str] = None
    needs_stdin = not args.paths or "-" in args.paths
    if needs_stdin and not sys.stdin.isatty():
        stdin_text = sys.stdin.read()

    if not args.paths and stdin_text is None:
        parser.print_usage(sys.stderr)
        print("promptdoctor: error: no input; pass a file, a directory, or pipe a prompt", file=sys.stderr)
        return 2

    results = _resolve_targets(args.paths, stdin_text, max_tokens=max_tokens, disable=disable)
    if not results:
        return 2

    stats = summarize(results)

    # --quiet silences the human report only; machine formats must stay parseable.
    if args.format == "json":
        print(render_json(results, version=__version__))
    elif args.format == "github":
        output = render_github(results)
        if output:
            print(output)
    elif not args.quiet:
        color = _use_color(args.no_color, sys.stdout)
        print(render_text(results, color=color))

    failing = stats["by_severity"]["error"] > 0 or (args.strict and stats["by_severity"]["warning"] > 0)
    return 1 if failing else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
