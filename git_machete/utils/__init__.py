"""Utility submodules used across `git_machete`.

The package intentionally has a near-empty `__init__.py` (no re-exports,
no shared globals): callers must import each symbol from its owning
submodule.

Layout:

* `._subproc`   - bare `subprocess` wrappers that never log
* `.cmd`        - high-level `run_cmd` / `popen_cmd` (with logging);
                  owns `verbose_mode`, `measure_command_time`,
                  `current_directory_confirmed_to_exist`
* `.collections`- generic iterable / sequence helpers
* `.date`       - current-date helper (separated from `.fs` so tests
                  can patch it without dragging in fs concerns)
* `.debug_log`  - `debug()` and friends; owns `debug_mode` and the
                  `CODE_HOSTING_TOKEN_*` constants
* `.exceptions` - exception classes and small enums
* `.fs`         - file-system helpers
* `.markup`     - markup language and styled output (`print_fmt`, ...);
                  owns `use_ansi_escapes_in_stdout` / `..._stderr`
* `.paths`      - POSIX-style path helpers
* `.terminal`   - TTY detection and ANSI escape-code constants

Mutable runtime flags live on the submodule that conceptually owns them
(rather than on this package object), so external callers reach them via
`from git_machete.utils import markup; markup.use_ansi_escapes_in_stdout`
etc., and submodules read them as ordinary module-level names.
"""
