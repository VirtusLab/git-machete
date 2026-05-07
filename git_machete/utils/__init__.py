"""Utility submodules used across `git_machete`.

The package intentionally has a near-empty `__init__.py` (no re-exports,
no shared globals): callers must import each symbol from its owning
submodule.

Layout:

* `._subproc`          - bare `subprocess` wrappers that never log
* `.terminal`          - TTY detection and ANSI escape-code constants
* `.paths`             - POSIX-style path helpers
* `.collections_utils` - generic iterable / sequence helpers
* `.markup`            - markup language and styled output (`print_fmt`, ...);
                         owns `use_ansi_escapes_in_stdout` / `..._stderr`
* `.debug_log`         - `debug()` and friends; owns `debug_mode` and the
                         `CODE_HOSTING_TOKEN_*` constants
* `.fs`                - file-system helpers
* `.cmd`               - high-level `run_cmd` / `popen_cmd` (with logging);
                         owns `verbose_mode`, `measure_command_time`,
                         `current_directory_confirmed_to_exist`
* `.exceptions`        - exception classes and small enums

Mutable runtime flags live on the submodule that conceptually owns them
(rather than on this package object), so external callers reach them via
`from git_machete.utils import markup; markup.use_ansi_escapes_in_stdout`
etc., and submodules read them as ordinary module-level names.
"""
