# promptdoctor

> A tiny, dependency-free static linter for LLM prompts.

[![CI](https://github.com/mhn0328/promptdoctor/actions/workflows/ci.yml/badge.svg)](https://github.com/mhn0328/promptdoctor/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/promptdoctor.svg)](https://pypi.org/project/promptdoctor/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)](pyproject.toml)

Prompts get shipped like code, but nothing checks them like code. `promptdoctor`
reads a prompt file and reports the structural problems that reviewers notice
too late: no output format, no length limit, vague quantifiers, a "be brief" and
"explain in detail" pair that fight each other, placeholders for third-party text
with no trust instruction.

It is one small Python package, zero dependencies, no API key, no network calls.
It never judges whether an answer is *good* - only whether a prompt is
*checkable*.

```console
$ promptdoctor examples/bad.md
```

```
examples/bad.md  ~116 tokens
            WARN  PD101  no output format is specified
            -> state the shape of the answer, e.g. "Return a JSON object with keys category, priority, summary."
            INFO  PD108  heavy emphasis (3 ALL-CAPS words, 5 '!')
            -> stacked emphasis is not a reliability knob; prefer explicit constraints and an example
  line 1    WARN  PD103  vague expression "some"
            -> replace it with a number, a range, or one concrete example
  line 2    WARN  PD104  prohibitions without a stated alternative
            -> models follow "do X instead of Y" far more reliably than "don't do Y"
  line 2    ERROR PD107  conflicting goals: "concise" and "in detail"
            -> pick one, or scope them: brief answer, then a separate detailed section
  line 7    WARN  PD105  placeholder '{{feedback}}' has no trust instruction
            -> when a placeholder holds third-party text, say that it is untrusted data and that instructions inside it must be ignored
  line 11   WARN  PD110  duplicated instruction (first seen on line 10)
            -> keep each instruction once: repetition costs tokens without improving compliance

7 findings in 1 prompt (1 error, 5 warning, 1 info) | ~116 tokens
```

Exit code is `1` when a rule at `error` severity fires, so it drops straight into
CI. Point it at [`examples/good.md`](examples/good.md) and it is quiet.

## Install

```console
pip install promptdoctor
```

Or from a clone, with no install at all:

```console
pip install git+https://github.com/mhn0328/promptdoctor.git
```

```console
git clone https://github.com/mhn0328/promptdoctor.git
cd promptdoctor
python -m pip install -e .
```

Requires Python 3.9+. No runtime dependencies.

## Usage

```console
promptdoctor prompts/                     # every .md/.txt/.prompt file in a folder
promptdoctor system.prompt user.prompt    # specific files
cat prompt.txt | promptdoctor             # stdin
promptdoctor --list-rules                 # rule table
promptdoctor prompts/ --max-tokens 4000   # relax the size budget
promptdoctor prompts/ --disable PD101,PD108
```

Useful flags:

| Flag | Meaning |
| --- | --- |
| `--format text\|json\|github` | human output (default), JSON for tooling, or GitHub Actions annotations |
| `--strict` | fail on warnings too, not just errors |
| `--max-tokens N` | size budget for `PD106` (default `2000`) |
| `--disable IDS` | comma-separated rule ids to skip |
| `--no-color` | plain text, also honoured via `NO_COLOR` |
| `-q`, `--quiet` | text mode: print nothing, keep the exit code |

`json` output is stable and shaped for scripts:

```console
$ promptdoctor examples/bad.md --format json | jq '.summary'
{
  "prompts": 1,
  "tokens": 116,
  "findings": 7,
  "by_severity": { "error": 1, "warning": 5, "info": 1 }
}
```

## Use as a pre-commit hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/mhn0328/promptdoctor
    rev: v0.2.1
    hooks:
      - id: promptdoctor
```

The hook runs on `.md`, `.txt`, `.prompt`, `.tmpl`, `.j2` and `.jinja` files.
`--strict` is not passed by default, so only `error`-severity findings block a
commit; add `args: [--strict]` if you want warnings to block too.

## Rules

| Rule | Severity | Catches |
| --- | --- | --- |
| `PD100` | error | empty prompt |
| `PD101` | warning | no output format requested |
| `PD102` | warning | no length limit given |
| `PD103` | warning | vague quantifiers ("some", "appropriate", "etc.") |
| `PD104` | warning | prohibitions ("don't…") with no stated alternative |
| `PD105` | warning | placeholder for external text with no trust instruction |
| `PD106` | info | prompt over the token budget |
| `PD107` | error | contradictory brevity / depth constraints |
| `PD108` | info | stacked emphasis (ALL-CAPS, `!!!`) |
| `PD110` | warning | duplicated instructions |

Every rule is a pure function in [`src/promptdoctor/rules.py`](src/promptdoctor/rules.py),
so adding one is a dozen lines plus a test.

## Use it in CI

```yaml
- name: Lint prompts
  run: |
    pip install git+https://github.com/mhn0328/promptdoctor.git
    promptdoctor prompts/ --strict --format github
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
- **No config file.** Flags are enough at this size; a `.promptdoctor.toml` would be
  pretending this is a bigger tool than it is.

## Development

```console
python -m unittest discover -s tests -v
```

```
src/promptdoctor/
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

`promptdoctor` 是一个零依赖的**提示词静态检查器（linter）**。它不调用任何模型、不需要 API key，
只检查提示词里那些"人评审时容易漏掉、上线后才发现"的结构问题：

- 没说要什么输出格式（`PD101`）、没限制长度（`PD102`）
- 模糊量词，比如"一些""合适的""等等"（`PD103`）
- 只说"不要做 X"，没说"要做什么"（`PD104`）
- 第三方内容占位符（如 `{{user_input}}`）没有"这是不可信数据、忽略其中的指令"这类防护（`PD105`）
- 提示词过长，超出 token 预算（`PD106`）
- 自相矛盾的要求，比如"简洁"又要求"详细展开"（`PD107`）
- 堆叠强调 `!!!`、全大写（`PD108`），以及重复的指令（`PD110`）

用法：

```console
pip install git+https://github.com/mhn0328/promptdoctor.git
promptdoctor prompts/ --strict          # 目录里所有 .md/.txt/.prompt
cat prompt.txt | promptdoctor           # 从标准输入
promptdoctor --list-rules               # 查看规则表
```

有 `error` 级问题时退出码为 `1`，`--strict` 下警告也计入失败，因此可以直接接进 CI；
`--format github` 会把问题渲染成 PR 行内批注。

注意：它是**启发式**检查，只判断"提示词是否可被检查"，不判断"提示词写得好不好"。
欢迎提交新的规则（一条规则 = 一个纯函数 + 一个测试）。
