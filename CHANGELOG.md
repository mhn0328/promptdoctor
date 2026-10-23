# Changelog

## 0.2.1

- Add `.pre-commit-hooks.yaml`, so the linter can run as a pre-commit hook
  (`repo: https://github.com/mhn0328/promptdoctor`).

## 0.2.0

- Rename the distribution to `promptdoctor`; the PyPI name `promptlint` belongs
  to an unrelated project and `prompt-lint` is rejected by PyPI as too similar.
- **Breaking:** rule ids move from `PL###` to `PD###`.
- Publish through PyPI Trusted Publishing from GitHub Actions; a tag push now
  releases the package with no stored token.

## 0.1.0

- First public release: 10 rules, text/JSON/GitHub Actions output, 34 tests,
  CI on Python 3.9-3.13 for Linux and Windows.
