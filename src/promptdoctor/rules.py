"""The rule set.

Every rule is a pure function of ``(Prompt, Context)`` returning findings, so
rules are trivially testable and easy to add. Rules describe *structural*
problems that a human reviewer usually catches late: a missing output format, a
constraint that contradicts another one, placeholders with no guard rail.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from .tokens import estimate_tokens

SEVERITY_LEVELS: Tuple[str, ...] = ("error", "warning", "info")

#: Findings at or above this severity make the CLI exit non-zero.
FAILING_SEVERITY = "error"


@dataclass(frozen=True)
class Finding:
    """One problem found in one prompt."""

    rule: str
    severity: str
    message: str
    line: Optional[int] = None
    hint: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "line": self.line,
            "hint": self.hint,
        }


@dataclass(frozen=True)
class Prompt:
    """A prompt under inspection."""

    text: str
    source: str = "<stdin>"

    @property
    def lines(self) -> List[str]:
        return self.text.splitlines()


@dataclass(frozen=True)
class Context:
    """Per-prompt facts computed once and shared by every rule."""

    max_tokens: int = 2000
    token_estimate: int = 0


@dataclass
class LintResult:
    """Findings for a single prompt."""

    source: str
    tokens: int
    findings: List[Finding] = field(default_factory=list)

    @property
    def counts(self) -> Dict[str, int]:
        counts = {level: 0 for level in SEVERITY_LEVELS}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts

    def worst_severity(self) -> Optional[str]:
        for level in SEVERITY_LEVELS:
            if any(f.severity == level for f in self.findings):
                return level
        return None

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "tokens": self.tokens,
            "findings": [f.as_dict() for f in self.findings],
        }


def _line_of(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


# -- PD100: nothing to lint -------------------------------------------------

def check_empty(prompt: Prompt, ctx: Context) -> List[Finding]:
    if prompt.text.strip():
        return []
    return [
        Finding(
            "PD100",
            "error",
            "prompt is empty",
            None,
            "a prompt needs at least a task description and an expected output",
        )
    ]


# -- PD101: no output format ------------------------------------------------

_FORMAT_RE = re.compile(
    r"\b(json|yaml|yml|markdown|md|table|csv|tsv|xml|html|sql|bullet(?:s|ed)?|"
    r"numbered list|code block|plain\s?text|schema|key-?value|to-?do list)\b"
    r"|```",
    re.I,
)


def check_output_format(prompt: Prompt, ctx: Context) -> List[Finding]:
    if _FORMAT_RE.search(prompt.text):
        return []
    return [
        Finding(
            "PD101",
            "warning",
            "no output format is specified",
            None,
            'state the shape of the answer, e.g. "Return a JSON object with keys category, priority, summary."',
        )
    ]


# -- PD102: no length constraint --------------------------------------------

_LENGTH_RE = re.compile(
    r"\b(?:\d+|one|two|three|four|five|a\s+single|a\s+few)\s+"
    r"(?:words?|characters?|chars?|sentences?|paragraphs?|bullets?|items?|lines?|tokens?|rows?)\b"
    r"|\b(?:brief(?:ly)?|concise|short|succinct|one-liner|tldr|tl;dr)\b"
    r"|\b(?:at most|no more than|maximum of|up to|not longer than)\b",
    re.I,
)


def check_length_constraint(prompt: Prompt, ctx: Context) -> List[Finding]:
    if _LENGTH_RE.search(prompt.text):
        return []
    return [
        Finding(
            "PD102",
            "warning",
            "no length limit is specified",
            None,
            'bound the answer, e.g. "at most 150 words" or "exactly 3 bullets"',
        )
    ]


# -- PD103: vague quantifiers ----------------------------------------------

_VAGUE_WORDS: Tuple[str, ...] = (
    "some",
    "a few",
    "several",
    "various",
    "appropriate",
    "as appropriate",
    "as needed",
    "etc.",
    "and so on",
    "reasonable",
    "proper",
    "if possible",
    "maybe",
    "roughly",
    "good quality",
    "best practices",
)


def check_vague_quantifiers(prompt: Prompt, ctx: Context) -> List[Finding]:
    lower = prompt.text.lower()
    hits: List[Tuple[str, int]] = []
    for word in _VAGUE_WORDS:
        match = re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", lower)
        if match:
            hits.append((word, _line_of(prompt.text, match.start())))

    findings = []
    for word, line in hits[:4]:
        findings.append(
            Finding(
                "PD103",
                "warning",
                f'vague expression "{word}"',
                line,
                "replace it with a number, a range, or one concrete example",
            )
        )
    return findings


# -- PD104: negative-only instruction --------------------------------------

_NEGATIVE_RE = re.compile(
    r"\b(don'?t|do not|never|avoid|must not|should not|shouldn'?t|cannot|can'?t)\b", re.I
)
_ALTERNATIVE_RE = re.compile(
    r"\b(instead|rather than|prefer|only|as an alternative|in other words|do this)\b", re.I
)


def check_negative_only(prompt: Prompt, ctx: Context) -> List[Finding]:
    negative = _NEGATIVE_RE.search(prompt.text)
    if not negative or _ALTERNATIVE_RE.search(prompt.text):
        return []
    return [
        Finding(
            "PD104",
            "warning",
            "prohibitions without a stated alternative",
            _line_of(prompt.text, negative.start()),
            'models follow "do X instead of Y" far more reliably than "don\'t do Y"',
        )
    ]


# -- PD105: unguarded placeholder ------------------------------------------

_PLACEHOLDER_RE = re.compile(
    r"\{\{[^{}\n]+\}\}"
    r"|\{[A-Za-z_][A-Za-z0-9_]*\}"
    r"|<[A-Za-z_][A-Za-z0-9_ ]{0,30}>"
    r"|\{\{[^{}]+\}\}"
    r"|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"
    r"|%\([a-z_]+\)s",
)
_GUARD_RE = re.compile(
    r"\b(untrusted|treat\b[^.\n]{0,40}\b(?:as|like)\b|delimited|verbatim|"
    r"ignore\s+(?:any\s+)?(?:previous|earlier|prior)\s+instructions|"
    r"do\s+not\s+follow\s+(?:any\s+)?instructions|data\s+only|as\s+data)\b",
    re.I,
)
_HTML_TAGS: Set[str] = {
    "a", "b", "br", "code", "div", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "i", "img", "italic", "li", "ol", "p", "pre", "s", "span", "strong",
    "table", "tbody", "td", "th", "thead", "tr", "u", "ul",
}


def check_placeholders(prompt: Prompt, ctx: Context) -> List[Finding]:
    if _GUARD_RE.search(prompt.text):
        return []

    for match in _PLACEHOLDER_RE.finditer(prompt.text):
        token = match.group(0)
        if token.startswith("<") and token.strip("<>").lower().strip() in _HTML_TAGS:
            continue
        return [
            Finding(
                "PD105",
                "warning",
                f"placeholder {token!r} has no trust instruction",
                _line_of(prompt.text, match.start()),
                "when a placeholder holds third-party text, say that it is untrusted data "
                "and that instructions inside it must be ignored",
            )
        ]
    return []


# -- PD106: token budget ---------------------------------------------------

def check_token_budget(prompt: Prompt, ctx: Context) -> List[Finding]:
    if ctx.token_estimate <= ctx.max_tokens:
        return []
    return [
        Finding(
            "PD106",
            "info",
            f"prompt is ~{ctx.token_estimate} tokens, above the {ctx.max_tokens}-token budget",
            None,
            "move stable instructions into a reusable prefix, or trim repeated boilerplate",
        )
    ]


# -- PD107: contradictory constraints --------------------------------------

_BREVITY_RE = re.compile(
    r"\b(brief(?:ly)?|concise|short|succinct|one-liner|tldr|tl;dr|summar(?:y|ize|ise))\b", re.I
)
_DEPTH_RE = re.compile(
    r"\b(in[- ]depth|in detail|step[- ]by[- ]step|thorough(?:ly)?|comprehensive|"
    r"exhaustive|elaborate|think (?:very )?(?:deeply|carefully)|"
    r"explain (?:your|the) reasoning|cover every)\b",
    re.I,
)


def check_conflicting_constraints(prompt: Prompt, ctx: Context) -> List[Finding]:
    brevity = _BREVITY_RE.search(prompt.text)
    depth = _DEPTH_RE.search(prompt.text)
    if not (brevity and depth):
        return []
    return [
        Finding(
            "PD107",
            "error",
            f'conflicting goals: "{brevity.group(0)}" and "{depth.group(0)}"',
            _line_of(prompt.text, depth.start()),
            "pick one, or scope them: brief answer, then a separate detailed section",
        )
    ]


# -- PD108: stacked emphasis ----------------------------------------------

_CAPS_RE = re.compile(r"\b[A-Z]{3,}\b")


def check_emphasis(prompt: Prompt, ctx: Context) -> List[Finding]:
    caps = _CAPS_RE.findall(prompt.text)
    bangs = prompt.text.count("!")
    if len(caps) < 4 and bangs < 3:
        return []
    return [
        Finding(
            "PD108",
            "info",
            f"heavy emphasis ({len(caps)} ALL-CAPS words, {bangs} '!')",
            None,
            "stacked emphasis is not a reliability knob; prefer explicit constraints "
            "and an example",
        )
    ]


# -- PD110: duplicated instructions ---------------------------------------

def check_duplicate_lines(prompt: Prompt, ctx: Context) -> List[Finding]:
    seen: Dict[str, int] = {}
    findings: List[Finding] = []
    for index, raw in enumerate(prompt.lines, start=1):
        line = " ".join(raw.split())
        if len(line) < 25:
            continue
        key = line.lower()
        if key in seen:
            findings.append(
                Finding(
                    "PD110",
                    "warning",
                    f"duplicated instruction (first seen on line {seen[key]})",
                    index,
                    "keep each instruction once: repetition costs tokens without "
                    "improving compliance",
                )
            )
        else:
            seen[key] = index
    return findings


# -- registry --------------------------------------------------------------

@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    summary: str
    check: Callable[[Prompt, Context], List[Finding]]


RULES: Tuple[Rule, ...] = (
    Rule("PD100", "error", "prompt is empty", check_empty),
    Rule("PD101", "warning", "no output format is specified", check_output_format),
    Rule("PD102", "warning", "no length limit is specified", check_length_constraint),
    Rule("PD103", "warning", "vague quantifiers", check_vague_quantifiers),
    Rule("PD104", "warning", "prohibitions without an alternative", check_negative_only),
    Rule("PD105", "warning", "unguarded placeholder for external content", check_placeholders),
    Rule("PD106", "info", "prompt exceeds the token budget", check_token_budget),
    Rule("PD107", "error", "contradictory brevity/depth constraints", check_conflicting_constraints),
    Rule("PD108", "info", "stacked emphasis", check_emphasis),
    Rule("PD110", "warning", "duplicated instructions", check_duplicate_lines),
)

RULES_BY_ID: Dict[str, Rule] = {rule.id: rule for rule in RULES}


def lint(
    text: str,
    source: str = "<stdin>",
    *,
    max_tokens: int = 2000,
    disable: Sequence[str] = (),
) -> LintResult:
    """Run every enabled rule over ``text`` and return the findings."""
    prompt = Prompt(text, source)
    ctx = Context(max_tokens=max_tokens, token_estimate=estimate_tokens(text))

    disabled = {d.strip().upper() for d in disable if d and d.strip()}
    unknown = disabled - set(RULES_BY_ID)
    if unknown:
        raise ValueError("unknown rule id(s): " + ", ".join(sorted(unknown)))

    findings: List[Finding] = []
    for rule in RULES:
        if rule.id in disabled:
            continue
        findings.extend(rule.check(prompt, ctx))

    findings.sort(key=lambda f: (f.line or 0, f.rule))
    return LintResult(source=source, tokens=ctx.token_estimate, findings=findings)
