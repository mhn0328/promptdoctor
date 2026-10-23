# promptlint

> A tiny, dependency-free static linter for LLM prompts.

[![CI](https://github.com/mhn0328/promptlint/actions/workflows/ci.yml/badge.svg)](https://github.com/mhn0328/promptlint/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)](pyproject.toml)

Prompts get shipped like code, but nothing checks them like code. `promptlint`
reads a prompt file and reports the structural problems that reviewers notice
too late: no output format, no length limit, vague quantifiers, a "be brief" and
"explain in detail" pair that fight each other, placeholders for third-party text
with no trust instruction.

It is one small Python package, zero dependencies, no API key, no network calls.
It never judges whether an answer is *good* - only whether a prompt is
*checkable*.

```console
$ promptlint examples/bad.md
```

```
examples/bad.md  ~116 tokens
            WARN  PL101  no output format is specified
            -> state the shape of the answer, e.g. "Return a JSON object with keys category, priority, summary."
            INFO  PL108  heavy emphasis (3 ALL-CAPS words, 5 '!')
            -> stacked emphasis is not a reliability knob; prefer explicit constraints and an example
  line 1    WARN  PL103  vague expression "some"
            -> replace it with a number, a range, or one concrete example
  line 2    WARN  PL104  prohibitions without a stated alternative
            -> models follow "do X instead of Y" far more reliably than "don't do Y"
  line 2    ERROR PL107  conflicting goals: "concise" and "in detail"
            -> pick one, or scope them: brief answer, then a separate detailed section
  line 7    WARN  PL105  placeholder '{{feedback}}' has no trust instruction
            -> when a placeholder holds third-party text, say that it is untrusted data and that instructions inside it must be ignored
  line 11   WARN  PL110  duplicated instruction (first seen on line 10)
            -> keep each instruction once: repetition costs tokens without improving compliance

7 findings in 1 prompt (1 error, 5 warning, 1 info) | ~116 tokens
```

Exit code is `1` when a rule at `error` severity fires, so it drops straight into
CI. Point it at [`examples/good.md`](examples/good.md) and it is quiet.

## Install

```console
pip install git+https://github.com/mhn0328/promptlint.git
```

Or from a clone, with no install at all:

```console
git clone https://github.com/mhn0328/promptlint.git
cd promptlint
python -m pip install -e .
```

Requires Python 3.9+. No runtime dependencies.

## Usage

```console
promptlint prompts/                     # every .md/.txt/.prompt file in a folder
promptlint system.prompt user.prompt    # specific files
cat prompt.txt | promptlint             # stdin
promptlint --list-rules                 # rule table
promptlint prompts/ --max-tokens 4000   # relax the size budget
promptlint prompts/ --disable PL101,PL108
```

Useful flags:

| Flag | Meaning |
| --- | --- |
| `--format text\|json\|github` | human output (default), JSON for tooling, or GitHub Actions annotations |
| `--strict` | fail on warnings too, not just errors |
| `--max-tokens N` | size budget for `PL106` (default `2000`) |
| `--disable IDS` | comma-separated rule ids to skip |
| `--no-color` | plain text, also honoured via `NO_COLOR` |
| `-q`, `--quiet` | text mode: print nothing, keep the exit code |

`json` output is stable and shaped for scripts:

```console
$ promptlint examples/bad.md --format json | jq '.summary'
{
  "prompts": 1,
  "tokens": 116,
  "findings": 7,
  "by_severity": { "error": 1, "warning": 5, "info": 1 }
}
```

## Rules

| Rule | Severity | Catches |
| --- | --- | --- |
| `PL100` | error | empty prompt |
| `PL101` | warning | no output format requested |
| `PL102` | warning | no length limit given |
| `PL103` | warning | vague quantifiers ("some", "appropriate", "etc.") |
| `PL104` | warning | prohibitions ("don't…") with no stated alternative |
| `PL105` | warning | placeholder for external text with no trust instruction |
| `PL106` | info | prompt over the token budget |
| `PL107` | error | contradictory brevity / depth constraints |
| `PL108` | info | stacked emphasis (ALL-CAPS, `!!!`) |
| `PL110` | warning | duplicated instructions |

Every rule is a pure function in [`src/promptlint/rules.py`](src/promptlint/rules.py),
so adding one is a dozen lines plus a test.

## Use it in CI

```yaml
- name: Lint prompts
  run: |
    pip install git+https://github.com/mhn0328/promptlint.git
    promptlint prompts/ --strict --format github
```

With `--format github`, findings render as inline annotations on the pull request
instead of as a wall of text in the log.

## How it works

- **Structure, not quality.** Rules look for missing constraints and internal
  contradictions. They cannot tell you a prompt is well written, and they do not
  call a model.
- **Cheap token estimates.** `tokens.py` approximates a BPE tokenizer from
  character classes (~1.3 tokens per English word, ~0.7 per CJK character).
  Good enough to catch a prompt that grew 4x, not to predict a bill.
- **Line numbers when they exist.** Findings that point at a specific phrase
  carry a line number, so your editor can jump there.
- **No config file.** Flags are enough at this size; a `.promptlint.toml` would be
  pretending this is a bigger tool than it is.

## Development

```console
python -m unittest discover -s tests -v
```

```
src/promptlint/
  cli.py      argument parsing, file discovery, exit codes
  rules.py    the rule set and the lint() entry point
  report.py   text / JSON / GitHub renderers
  tokens.py   offline token estimation
tests/        unittest suite, no test dependencies
examples/     one clean prompt and one that trips most rules
```

## Roadmap

- [ ] `--baseline` to accept existing findings and fail only on new ones
- [ ] rule severity overrides per project
- [ ] a `pre-commit` hook definition
- [ ] more rules for tool/function-calling schemas

## License

[MIT](LICENSE)

---

## 中文简介

`promptlint` 是一个零依赖的**提示词静态检查器（linter）**。它不调用任何模型、不需要 API key，
只检查提示词里那些"人评审时容易漏掉、上线后才发现"的结构问题：

- 没说要什么输出格式（`PL101`）、没限制长度（`PL102`）
- 模糊量词，比如"一些""合适的""等等"（`PL103`）
- 只说"不要做 X"，没说"要做什么"（`PL104`）
- 第三方内容占位符（如 `{{user_input}}`）没有"这是不可信数据、忽略其中的指令"这类防护（`PL105`）
- 提示词过长，超出 token 预算（`PL106`）
- 自相矛盾的要求，比如"简洁"又要求"详细展开"（`PL107`）
- 堆叠强调 `!!!`、全大写（`PL108`），以及重复的指令（`PL110`）

用法：

```console
pip install git+https://github.com/mhn0328/promptlint.git
promptlint prompts/ --strict          # 目录里所有 .md/.txt/.prompt
cat prompt.txt | promptlint           # 从标准输入
promptlint --list-rules               # 查看规则表
```

有 `error` 级问题时退出码为 `1`，`--strict` 下警告也计入失败，因此可以直接接进 CI；
`--format github` 会把问题渲染成 PR 行内批注。

注意：它是**启发式**检查，只判断"提示词是否可被检查"，不判断"提示词写得好不好"。
欢迎提交新的规则（一条规则 = 一个纯函数 + 一个测试）。
