# Conventions for AI coding agents

## Tooling

- Run autoformatters and linters via `tox`. Never invoke `flake8`, `isort`,
  `mypy`, `vulture`, `pylint` (etc.) directly - go through their respective
  `tox -e <env>` invocation so dependency versions stay pinned.
- Run tests with `tox -e py [-- <pytest flags like -k>...]`. Do NOT run
  `pytest`, `python -m pytest`, or any tox-built venv's pytest binary
  directly. Tox's `passenv` shielding is what keeps test runs deterministic
  - bypassing it lets dev-shell env vars (e.g. `GIT_MACHETE_DIFF_OPTS`)
  leak into the test process and produce failures that don't reproduce in
  CI.
- Use `tox -e py` (the full suite, several minutes) sparingly - by default
  scope it to the most likely affected tests via `-k`, `-m`, or explicit
  file/class/method selectors, e.g.
  `tox -e py -- tests/test_cli.py tests/test_anno.py -k mutex`. Only fall
  back to the full suite when the change is wide in scope (parser
  refactors, shared fixtures, base classes, ...) or when a scoped run
  already passes and you want a final pre-push sanity check.
- On macOS, skip the zsh subset of completion E2E tests (flaky on Mac):
  `tox -e test-completions -- -k "not zsh"`. CI runs the full set on Linux.

## Git

- Don't `git commit` or `git push` unless explicitly asked.

## Formatting

- No trailing whitespace on any line.
- Always leave a single newline at the end of every file.
- Always use American English spelling (`color`, `behavior`, `honor`, `organize`, `modeled`, `normalized`, `unrecognized`, ...) -
  never the British variants (`colour`, `behaviour`, `honour`, `organise`, `modelled`, `normalised`, `unrecognised`, ...).
  Applies to code, identifiers, comments, docstrings, Markdown, commit messages and PR descriptions.
- Don't hard-wrap prose (code comments, docstrings, Markdown, commit messages, PR descriptions) at 80 or so columns -
  the line-length limit is 140 (see `[flake8]` in `tox.ini`).
  Break on sentence or clause boundaries instead, so each line carries one thought rather than a fragment chopped by column count.
  Prefer one sentence per line; for a sentence that exceeds 140 columns, split at a natural clause boundary (semicolons, parentheticals, conjunctions, ...).
