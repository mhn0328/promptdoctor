"""Rendering of lint results: human text, JSON, and GitHub Actions annotations."""

from __future__ import annotations

import json
from typing import Iterable, List, Sequence

from .rules import LintResult

_COLORS = {
    "error": "\x1b[31m",
    "warning": "\x1b[33m",
    "info": "\x1b[36m",
    "dim": "\x1b[2m",
    "bold": "\x1b[1m",
    "reset": "\x1b[0m",
}

_LABELS = {"error": "ERROR", "warning": "WARN ", "info": "INFO "}

_GH_LEVELS = {"error": "error", "warning": "warning", "info": "notice"}


def _paint(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{_COLORS.get(color, '')}{text}{_COLORS['reset']}"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def summarize(results: Sequence[LintResult]) -> dict:
    """Aggregate counts across results."""
    totals = {"error": 0, "warning": 0, "info": 0}
    for result in results:
        for level, count in result.counts.items():
            totals[level] = totals.get(level, 0) + count
    return {
        "prompts": len(results),
        "tokens": sum(r.tokens for r in results),
        "findings": sum(totals.values()),
        "by_severity": totals,
    }


def render_text(results: Sequence[LintResult], *, color: bool = True) -> str:
    lines: List[str] = []
    for result in results:
        header = f"{result.source}  {_paint(f'~{result.tokens} tokens', 'dim', color)}"
        lines.append(_paint(header, "bold", color))
        if not result.findings:
            lines.append(f"  {_paint('clean', 'dim', color)}")
        for finding in result.findings:
            location = f"line {finding.line}" if finding.line else "      "
            label = _paint(_LABELS.get(finding.severity, "????? "), finding.severity, color)
            lines.append(f"  {location:<9} {label} {finding.rule}  {finding.message}")
            if finding.hint:
                lines.append(f"{'':<12}{_paint('-> ' + finding.hint, 'dim', color)}")
        lines.append("")

    stats = summarize(results)
    parts = [f"{stats['findings']} findings in {_plural(stats['prompts'], 'prompt')}"]
    details = ", ".join(
        f"{count} {level}" for level, count in stats["by_severity"].items() if count
    )
    summary = parts[0] + (f" ({details})" if details else "") + f" | ~{stats['tokens']} tokens"
    lines.append(_paint(summary, "bold", color))
    return "\n".join(lines)


def render_json(results: Sequence[LintResult], *, version: str = "") -> str:
    payload = {
        "version": version,
        "summary": summarize(results),
        "results": [result.as_dict() for result in results],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_github(results: Sequence[LintResult]) -> str:
    lines: List[str] = []
    for result in results:
        for finding in result.findings:
            level = _GH_LEVELS.get(finding.severity, "notice")
            location = f"file={result.source}"
            if finding.line:
                location += f",line={finding.line}"
            message = f"{finding.rule} {finding.message}"
            if finding.hint:
                message += f" — {finding.hint}"
            message = message.replace("\n", " ")
            lines.append(f"::{level} {location}::{message}")
    return "\n".join(lines)


def render_rule_list(rules: Iterable, *, color: bool = True) -> str:
    rows = [f"{rule.id}  {rule.severity:<7}  {rule.summary}" for rule in rules]
    return "\n".join(rows)
