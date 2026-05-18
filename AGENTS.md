# Conventions for AI coding agents

## Tooling

- Run autoformatters and linters via `tox`. Never invoke `flake8`, `isort`,
  `mypy`, `vulture`, `pylint` (etc.) directly - go through their respective
  `tox -e <env>` invocation so dependency versions stay pinned.
- Exception: do NOT run `tox -e flake8` or `tox -e vulture` (or those binaries directly).
  They hang indefinitely inside Cursor's terminal for an unidentified reason - rely on CI to catch any violations.
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

## Tests

- Skip tests that require a minimum Git version with `@pytest.mark.skipif(get_git_version() < (X, Y), reason="...")`,
  not with an `if get_git_version() < (X, Y): return` early-return at the top of the test body.
  The decorator surfaces the skip in pytest's report (and in the JUnit XML CI uploads); the early-return silently masquerades as a pass.

## Comments

- Don't add code comments that narrate test-harness internals or explain why an assertion's expected value was massaged
  to match the harness's output (e.g. "backticks are stripped by `_fmt` in ASCII mode, so the expected string omits them",
  "the harness lower-cases this, so we compare against lower-case", etc.).
  If the actual and expected values match, the assertion already documents itself; if they don't, fix the production code or the harness, don't annotate the workaround.
  This generalizes: avoid comments that exist solely to justify a specific literal in a test - the test name and the assertion are the contract.

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
