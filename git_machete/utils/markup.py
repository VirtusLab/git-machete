"""Markup formatting and styled output helpers.

The markup language is intentionally tiny - a handful of `<tag>...</tag>`
blocks plus a few self-closing tags - and is rendered to either ANSI escape
sequences or plain ASCII depending on whether the destination stream is a
TTY (and on `--color`).

`_fmt` looks up :func:`is_terminal_fully_fledged` indirectly through the
parent :mod:`git_machete.utils` namespace, so that :func:`unittest.mock.patch`
on `git_machete.utils.is_terminal_fully_fledged` (used heavily in tests) keeps
working after the module split.
"""

import re
import sys
from typing import Any, List, Optional, Tuple

from .collections_utils import map_truthy_only
from .terminal import BasicTerminalAnsiOutputCodes, FullTerminalAnsiOutputCodes

# Note: `git_machete.utils` (the parent package) is imported lazily inside the
# functions that need it - both to break the package <-> submodule import cycle
# that pylint's `cyclic-import` check would otherwise flag, and so that
# `unittest.mock.patch('git_machete.utils.is_terminal_fully_fledged', ...)` and
# external assignments to `utils.use_ansi_escapes_in_*` are picked up at every
# call (the package object holds the canonical bindings).


def escape_markup(s: str) -> str:
    """Escape characters that `_fmt` would interpret as markup.

    Use on user-provided content (annotation text, commit subjects, hook
    output) before embedding it into markup strings.
    """
    return s.replace('&', '&amp;').replace('`', '&backtick;').replace('<', '&lt;')


def _fmt(s: str, *, use_ansi_escapes: bool) -> str:
    from git_machete import utils as _utils

    # Looked up via the parent package so that `mock.patch('git_machete.utils.is_terminal_fully_fledged', ...)`
    # in tests is honoured - rebinding the attribute on the package replaces the value seen here.
    ao = FullTerminalAnsiOutputCodes if _utils.is_terminal_fully_fledged() else BasicTerminalAnsiOutputCodes

    # pattern                                  ansi replacement                            ascii replacement
    rules: List[Tuple[str, str, str]] = [
        ('`(.*?)`',                           f'{ao.UNDERLINE}\\1{ao.ENDC_UNDERLINE}',    r'\1'),              # noqa: E241
        ('<u>(.*?)</u>',                      f'{ao.UNDERLINE}\\1{ao.ENDC_UNDERLINE}',    r'\1'),              # noqa: E241
        ('<b>(.*?)</b>',                      f'{ao.BOLD}\\1{ao.ENDC_BOLD_DIM}',          r'\1'),              # noqa: E241
        ('<dim>(.*?)</dim>',                  f'{ao.DIM}\\1{ao.ENDC_BOLD_DIM}',           r'\1'),              # noqa: E241
        ('<gray>(.*?)</gray>',                f'{ao.DIM}\\1{ao.ENDC_BOLD_DIM}',           r'\1'),              # noqa: E241
        ('<red>(.*?)</red>',                  f'{ao.RED}\\1{ao.ENDC}',                    r'\1'),              # noqa: E241
        ('<orange>(.*?)</orange>',            f'{ao.ORANGE}\\1{ao.ENDC}',                 r'\1'),              # noqa: E241
        ('<yellow>(.*?)</yellow>',            f'{ao.YELLOW}\\1{ao.ENDC}',                 r'\1'),              # noqa: E241
        ('<green>(.*?)</green>',              f'{ao.GREEN}\\1{ao.ENDC}',                  r'\1'),              # noqa: E241
        ('<reverse>(.*?)</reverse>',          f'{ao.REVERSE_VIDEO}\\1{ao.ENDC}',          r'\1'),              # noqa: E241
        ('<vbar/>',                            '│',                                        '|'),               # noqa: E241
        ('<rarrow/>',                          '➔',                                        '->'),              # noqa: E241
        ('<ifansi>(.*?)<else>(.*?)</ifansi>', r'\1',                                      r'\2'),              # noqa: E241
        ('&backtick;',                         '`',                                        '`'),               # noqa: E241
        ('&lt;',                               '<',                                        '<'),               # noqa: E241
        ('&amp;',                              '&',                                        '&'),               # noqa: E241
    ]

    result = s
    for pattern, ansi_repl, ascii_repl in rules:
        result = re.sub(pattern, ansi_repl if use_ansi_escapes else ascii_repl, result, flags=re.DOTALL)
    return result


def print_fmt(s: str, *, file: Optional[Any] = None, newline: bool = True) -> None:
    """Format `s` with `_fmt` for the stream `file`, then print.

    ANSI / Unicode styling follows the same rules as for direct writes to `file`
    (stdout vs stderr, TTY detection, `--color`, etc.).

    When newline=False, output is flushed immediately so that a
    subsequent print_fmt (e.g. "OK") appears on the same line
    without delay.
    """
    from git_machete import utils as _utils

    use_ansi = _utils.use_ansi_escapes_in_stderr if file is sys.stderr else _utils.use_ansi_escapes_in_stdout
    # Defaults to stdout at call time so that contextlib.redirect_stdout is respected.
    if file is None:
        file = sys.stdout
    content = _fmt(s, use_ansi_escapes=use_ansi)
    print(content, file=file, end='\n' if newline else '', flush=not newline)


def input_fmt(prompt: str) -> str:
    from git_machete import utils as _utils

    return input(_fmt(prompt, use_ansi_escapes=_utils.use_ansi_escapes_in_stdout))


def warn(msg: str) -> None:
    print_fmt(f"<orange>Warn: </orange>{msg}", file=sys.stderr)


def green_ok() -> str:
    return '<green><b>OK</b></green>'


def pretty_choices(*choices: str) -> str:
    def format_choice(c: str) -> str:
        if not c:
            return ''
        elif c.lower() == 'y':
            return f'<green>{c}</green>'
        elif c.lower() == 'yq':
            return f'<green>{c[0]}</green><red>{c[1]}</red>'
        elif c.lower() in ('n', 'q'):
            return f'<red>{c}</red>'
        else:
            return f'<orange>{c}</orange>'

    return " (" + (", ".join(map_truthy_only(format_choice, choices))) + ") "


def colored_yes_no(value: bool) -> str:  # noqa: KW
    return '<green><b>YES</b></green>' if value else '<red><b>NO</b></red>'
