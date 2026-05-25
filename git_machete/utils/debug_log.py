"""Debug-mode logging.

`debug` is a no-op unless `debug_mode` is set (typically because `--debug` was passed on the command line).
It pulls argument names and values directly from the caller's frame via `inspect`.
"""

import inspect
import re
import sys
import textwrap
from typing import Any, Dict

from git_machete.utils.collections import excluding
from git_machete.utils.markup import escape_markup, print_fmt

# === Mutable runtime flags ===
#
# Set by `cli.py` based on `--debug`; read here and (for command logging)
# also by `cmd.py`.
debug_mode: bool = False

# === Token-redaction constants ===
#
# https://github.blog/2021-04-05-behind-githubs-new-authentication-token-formats/
# https://docs.gitlab.com/ee/security/token_overview.html#gitlab-tokens
CODE_HOSTING_TOKEN_PREFIXES = ['ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_', 'glpat-']
CODE_HOSTING_TOKEN_PREFIX_REGEX = '(' + '|'.join(CODE_HOSTING_TOKEN_PREFIXES) + ')'


def hex_repr(input: str) -> str:
    return ':'.join(hex(ord(char))[2:] for char in input)


def compact_dict(d: Dict[str, Any]) -> Dict[str, str]:
    return {k: re.sub('\n +', ' ', str(v)) for k, v in d.items()}


def debug(msg: str) -> None:
    if not debug_mode:
        return

    func = inspect.stack()[1].function
    args, _, _, values_original = inspect.getargvalues(inspect.stack()[1].frame)
    # Do not write over the original values!
    # Since Python 3.13, the result of `getargvalues` keeps a map of local variables that the Python runtime actually keeps on the stack,
    # so overwriting a key in values_original changes the local variable.
    values: Dict[str, Any] = dict(values_original)

    args_to_be_redacted = {'access_token', 'password', 'secret', 'token'}
    for arg, value in values.items():
        if arg in args_to_be_redacted or any(prefix in str(value) for prefix in CODE_HOSTING_TOKEN_PREFIXES):
            values[arg] = '***'
        elif type(value) is dict:
            values[arg] = compact_dict(value)
        values[arg] = textwrap.shorten(str(values[arg]), width=50, placeholder="...")

    args_and_values_list = [arg + '=' + str(values[arg]) for arg in excluding(args, {'self'})]
    args_and_values_str = ', '.join(args_and_values_list)

    escaped_args = escape_markup(args_and_values_str)
    print_fmt(f"<b>{func}</b><b>({escaped_args})</b>: <dim>{msg}</dim>", file=sys.stderr)
