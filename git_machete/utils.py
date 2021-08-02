
from typing import Any, Callable, Iterable, List, Optional, Tuple, TypeVar, Dict

import os
import sys
import re
import subprocess

from git_machete.contexts import CommandLineContext

T = TypeVar('T')


def excluding(iterable: Iterable[T], s: Iterable[T]) -> List[T]:
    return list(filter(lambda x: x not in s, iterable))


def flat_map(func: Callable[[T], List[T]], iterable: Iterable[T]) -> List[T]:
    return sum(map(func, iterable), [])


def map_truthy_only(func: Callable[[T], Optional[T]], iterable: Iterable[T]) -> List[T]:
    return list(filter(None, map(func, iterable)))


def non_empty_lines(s: str) -> List[str]:
    return list(filter(None, s.split("\n")))


# Converts a lambda accepting N arguments to a lambda accepting one argument, an N-element tuple.
# Name matching Scala's `tupled` on `FunctionX`.
def tupled(f: Callable[..., T]) -> Callable[[Any], T]:
    return lambda tple: f(*tple)


def get_second(pair: Tuple[str, str]) -> str:
    a, b = pair
    return b


def directory_exists(path: str) -> bool:
    try:
        # Note that os.path.isdir itself (without os.path.abspath) isn't reliable
        # since it returns a false positive (True) for the current directory when if it doesn't exist
        return os.path.isdir(os.path.abspath(path))
    except OSError:
        return False


def current_directory_or_none() -> Optional[str]:
    try:
        return os.getcwd()
    except OSError:
        # This happens when current directory does not exist (typically: has been deleted)
        return None


def is_executable(path: str) -> bool:
    return os.access(path, os.X_OK)


def find_executable(cli_ctxt: CommandLineContext, executable: str) -> Optional[str]:
    base, ext = os.path.splitext(executable)

    if (sys.platform == 'win32' or os.name == 'os2') and (ext != '.exe'):
        executable = f"{executable}.exe"

    if os.path.isfile(executable):
        return executable

    path = os.environ.get('PATH', os.defpath)
    paths = path.split(os.pathsep)
    for p in paths:
        f = os.path.join(p, executable)
        if os.path.isfile(f) and is_executable(f):
            debug(cli_ctxt, f"find_executable({executable})", f"found {executable} at {f}")
            return f
    return None


ENDC = '\033[0m'
BOLD = '\033[1m'
# `GIT_MACHETE_DIM_AS_GRAY` remains undocumented as for now,
# was just needed for animated gifs to render correctly (`[2m`-style dimmed text was invisible)
DIM = '\033[38;2;128;128;128m' if os.environ.get('GIT_MACHETE_DIM_AS_GRAY') == 'true' else '\033[2m'
UNDERLINE = '\033[4m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[00;38;5;208m'
RED = '\033[91m'

ascii_only: bool = True


def bold(s: str) -> str:
    return s if ascii_only or not s else BOLD + s + ENDC


def dim(s: str) -> str:
    return s if ascii_only or not s else DIM + s + ENDC


def underline(s: str, star_if_ascii_only: bool = False) -> str:
    if s and not ascii_only:
        return UNDERLINE + s + ENDC
    elif s and star_if_ascii_only:
        return s + " *"
    else:
        return s


def colored(s: str, color: str) -> str:
    return s if ascii_only or not s else color + s + ENDC


fmt_transformations: List[Callable[[str], str]] = [
    lambda x: re.sub('<b>(.*?)</b>', bold(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<u>(.*?)</u>', underline(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<dim>(.*?)</dim>', dim(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<red>(.*?)</red>', colored(r"\1", RED), x, flags=re.DOTALL),
    lambda x: re.sub('<yellow>(.*?)</yellow>', colored(r"\1", YELLOW), x, flags=re.DOTALL),
    lambda x: re.sub('<green>(.*?)</green>', colored(r"\1", GREEN), x, flags=re.DOTALL),
    lambda x: re.sub('`(.*?)`', r"`\1`" if ascii_only else UNDERLINE + r"\1" + ENDC, x),
]


def fmt(*parts: str) -> str:
    result = ''.join(parts)
    for f in fmt_transformations:
        result = f(result)
    return result


def vertical_bar() -> str:
    return "|" if ascii_only else u"│"


def right_arrow() -> str:
    return "->" if ascii_only else u"➔"


def pretty_choices(*choices: str) -> str:
    def format_choice(c: str) -> str:
        if not c:
            return ''
        elif c.lower() == 'y':
            return colored(c, GREEN)
        elif c.lower() == 'yq':
            return colored(c[0], GREEN) + colored(c[1], RED)
        elif c.lower() in ('n', 'q'):
            return colored(c, RED)
        else:
            return colored(c, ORANGE)
    return f" ({', '.join(map_truthy_only(format_choice, choices))}) "


def debug(cli_ctxt: CommandLineContext, hdr: str, msg: str) -> None:
    if cli_ctxt.opt_debug:
        sys.stderr.write(f"{bold(hdr)}: {dim(msg)}\n")


def run_cmd(cli_ctxt: CommandLineContext, cmd: str, *args: str, **kwargs: Any) -> int:
    chdir_upwards_until_current_directory_exists(cli_ctxt)

    flat_cmd: str = cmd_shell_repr(cmd, *args, **kwargs)
    if cli_ctxt.opt_debug:
        sys.stderr.write(bold(f">>> {flat_cmd}") + "\n")
    elif cli_ctxt.opt_verbose:
        sys.stderr.write(flat_cmd + "\n")

    exit_code: int = subprocess.call([cmd] + list(args), **kwargs)

    # Let's defensively assume that every command executed via run_cmd
    # (but not via popen_cmd) can make the current directory disappear.
    # In practice, it's mostly 'git checkout' that carries such risk.
    mark_current_directory_as_possibly_non_existent()

    if cli_ctxt.opt_debug and exit_code != 0:
        sys.stderr.write(dim(f"<exit code: {exit_code}>\n\n"))
    return exit_code


current_directory_confirmed_to_exist: bool = False


def mark_current_directory_as_possibly_non_existent() -> None:
    global current_directory_confirmed_to_exist
    current_directory_confirmed_to_exist = False


def chdir_upwards_until_current_directory_exists(cli_ctxt: CommandLineContext) -> None:
    global current_directory_confirmed_to_exist
    if not current_directory_confirmed_to_exist:
        current_directory: Optional[str] = current_directory_or_none()
        if not current_directory:
            while not current_directory:
                # Note: 'os.chdir' only affects the current process and its subprocesses;
                # it doesn't propagate to the parent process (which is typically a shell).
                os.chdir(os.path.pardir)
                current_directory = current_directory_or_none()
            debug(cli_ctxt,
                  "chdir_upwards_until_current_directory_exists()",
                  f"current directory did not exist, chdired up into {current_directory}")
        current_directory_confirmed_to_exist = True


def popen_cmd(cli_ctxt: CommandLineContext, cmd: str, *args: str, **kwargs: Any) -> Tuple[int, str, str]:
    chdir_upwards_until_current_directory_exists(cli_ctxt)

    flat_cmd = cmd_shell_repr(cmd, *args, **kwargs)
    if cli_ctxt.opt_debug:
        sys.stderr.write(bold(f">>> {flat_cmd}") + "\n")
    elif cli_ctxt.opt_verbose:
        sys.stderr.write(flat_cmd + "\n")

    process = subprocess.Popen([cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    stdout_bytes, stderr_bytes = process.communicate()
    stdout: str = stdout_bytes.decode('utf-8')
    stderr: str = stderr_bytes.decode('utf-8')
    exit_code: int = process.returncode

    if cli_ctxt.opt_debug:
        if exit_code != 0:
            sys.stderr.write(colored(f"<exit code: {exit_code}>\n\n", RED))
        if stdout:
            sys.stderr.write(f"{dim('<stdout>:')}\n{dim(stdout)}\n")
        if stderr:
            sys.stderr.write(f"{dim('<stderr>:')}\n{colored(stderr, RED)}\n")

    return exit_code, stdout, stderr


def cmd_shell_repr(cmd: str, *args: str, **kwargs: Dict[str, str]) -> str:
    def shell_escape(arg: str) -> str:
        return arg.replace("(", "\\(") \
            .replace(")", "\\)") \
            .replace(" ", "\\ ") \
            .replace("\t", "$'\\t'") \
            .replace("\n", "$'\\n'")

    env: Dict[str, str] = kwargs.get("env", {})
    # We don't want to include the env vars that are inherited from the environment of git-machete process
    env_repr = [k + "=" + shell_escape(v) for k, v in env.items() if k not in os.environ]
    return " ".join(env_repr + [cmd] + list(map(shell_escape, args)))
