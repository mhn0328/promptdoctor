"""Tests for the command line interface."""

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from promptlint.cli import main  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOOD = str(ROOT / "examples" / "good.md")
BAD = str(ROOT / "examples" / "bad.md")


def run_cli(argv, stdin_text=None):
    """Run main() capturing stdout/stderr; returns (code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    stdin_patch = mock.patch("sys.stdin", io.StringIO(stdin_text)) if stdin_text is not None else mock.patch(
        "sys.stdin", io.StringIO("")
    )
    with stdin_patch, redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def test_clean_prompt_exits_zero(self):
        code, out, _ = run_cli([GOOD])
        self.assertEqual(code, 0)
        self.assertIn("clean", out)

    def test_bad_prompt_exits_one(self):
        code, out, _ = run_cli([BAD])
        self.assertEqual(code, 1)
        self.assertIn("PL107", out)

    def test_json_format_is_valid_json(self):
        code, out, _ = run_cli([BAD, "--format", "json"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertEqual(payload["summary"]["prompts"], 1)
        self.assertTrue(payload["results"][0]["findings"])
        self.assertIn("tokens", payload["results"][0])

    def test_github_format_uses_workflow_commands(self):
        _, out, _ = run_cli([BAD, "--format", "github"])
        first = out.splitlines()[0]
        self.assertTrue(first.startswith("::error ") or first.startswith("::warning "))
        self.assertIn("file=", first)

    def test_stdin_is_linted(self):
        code, out, _ = run_cli([], stdin_text="Give me some ideas.\n")
        self.assertEqual(code, 0)  # warnings only: exit stays 0
        self.assertIn("<stdin>", out)
        self.assertIn("PL103", out)

    def test_strict_promotes_warnings_to_failures(self):
        warning_only = "Summarise the note below.\n"
        code, _, _ = run_cli([], stdin_text=warning_only)
        self.assertEqual(code, 0)
        code_strict, _, _ = run_cli(["--strict"], stdin_text=warning_only)
        self.assertEqual(code_strict, 1)

    def test_clean_prompt_passes_strict(self):
        clean = "Summarise the note in JSON, at most 40 words.\n"
        code, _, _ = run_cli(["--strict"], stdin_text=clean)
        self.assertEqual(code, 0)

    def test_disable_flag_skips_rules(self):
        _, out, _ = run_cli([BAD, "--disable", "PL107,PL108"])
        self.assertNotIn("PL107", out)
        self.assertNotIn("PL108", out)
        self.assertIn("PL110", out)

    def test_unknown_rule_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            run_cli([GOOD, "--disable", "PL999"])
        self.assertEqual(ctx.exception.code, 2)

    def test_list_rules(self):
        code, out, _ = run_cli(["--list-rules"])
        self.assertEqual(code, 0)
        self.assertIn("PL101", out)
        self.assertIn("PL107", out)

    def test_quiet_prints_nothing_in_text_mode(self):
        code, out, _ = run_cli([BAD, "--quiet"])
        self.assertEqual(code, 1)
        self.assertEqual(out.strip(), "")

    def test_quiet_keeps_json_parseable(self):
        _, out, _ = run_cli([BAD, "--format", "json", "--quiet"])
        self.assertEqual(json.loads(out)["summary"]["prompts"], 1)

    def test_missing_path_exits_two(self):
        code, _, err = run_cli([str(ROOT / "does-not-exist.prompt")])
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)

    def test_directory_input(self):
        code, out, _ = run_cli([str(ROOT / "examples")])
        self.assertEqual(code, 1)
        self.assertIn("good.md", out)
        self.assertIn("bad.md", out)


if __name__ == "__main__":
    unittest.main()
