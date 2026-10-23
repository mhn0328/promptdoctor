"""promptdoctor - a small, dependency-free static linter for LLM prompts."""

from .rules import RULES, Context, Finding, LintResult, Prompt, Rule, lint
from .tokens import estimate_tokens

__version__ = "0.2.1"

__all__ = [
    "RULES",
    "Context",
    "Finding",
    "LintResult",
    "Prompt",
    "Rule",
    "__version__",
    "estimate_tokens",
    "lint",
]
