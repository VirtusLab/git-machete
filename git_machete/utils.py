
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, TypeVar

import os
import sys
import re
import subprocess

from git_machete.constants import EscapeCodes

T = TypeVar('T')
# To avoid displaying the same warning multiple times during a single run.
displayed_warnings: Set[str] = set()

# Let's keep the flag to avoid checking for current directory's existence
# every time any command is being popened or run.
current_directory_confirmed_to_exist: bool = False

ascii_only: bool = False
debug_mode: bool = False
verbose_mode: bool = False


def excluding(iterable: Iterable[T], s: Iterable[T]) -> List[T]:
    return list(filter(lambda x: x not in s, iterable))


def flat_map(func: Callable[[T], List[T]], iterable: Iterable[T]) -> List[T]:
    return sum(map(func, iterable), [])


def find_or_none(func: Callable[[T], bool], iterable: Iterable[T]) -> T:
    return next(filter(func, iterable), None)


def map_truthy_only(func: Callable[[T], Optional[T]], iterable: Iterable[T]) -> List[T]:
    return list(filter(None, map(func, iterable)))


def get_non_empty_lines(s: str) -> List[str]:
    return list(filter(None, s.split("\n")))


# Converts a lambda accepting N arguments to a lambda accepting one argument, an N-element tuple.
# Name matching Scala's `tupled` on `FunctionX`.
def tupled(f: Callable[..., T]) -> Callable[[Any], T]:
    return lambda tple: f(*tple)


def get_second(pair: Tuple[Any, T]) -> T:
    a, b = pair
    return b


def does_directory_exist(path: str) -> bool:
    try:
        # Note that os.path.isdir itself (without os.path.abspath) isn't reliable
        # since it returns a false positive (True) for the current directory when if it doesn't exist
        return os.path.isdir(os.path.abspath(path))
    except OSError:
        return False


def get_current_directory_or_none() -> Optional[str]:
    try:
        return os.getcwd()
    except OSError:
        # This happens when current directory does not exist (typically: has been deleted)
        return None


def is_executable(path: str) -> bool:
    return os.access(path, os.X_OK)


def find_executable(executable: str) -> Optional[str]:
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
            debug(f"find_executable({executable})", f"found {executable} at {f}")
            return f
    return None


def bold(s: str) -> str:
    return s if ascii_only or not s else EscapeCodes.BOLD + s + EscapeCodes.ENDC


def dim(s: str) -> str:
    return s if ascii_only or not s else EscapeCodes.DIM + s + EscapeCodes.ENDC


def underline(s: str, star_if_ascii_only: bool = False) -> str:
    if s and not ascii_only:
        return EscapeCodes.UNDERLINE + s + EscapeCodes.ENDC
    elif s and star_if_ascii_only:
        return s + " *"
    else:
        return s


def colored(s: str, color: str) -> str:
    return s if ascii_only or not s else color + s + EscapeCodes.ENDC


fmt_transformations: List[Callable[[str], str]] = [
    lambda x: re.sub('<b>(.*?)</b>', bold(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<u>(.*?)</u>', underline(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<dim>(.*?)</dim>', dim(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<red>(.*?)</red>', colored(r"\1", EscapeCodes.RED), x, flags=re.DOTALL),
    lambda x: re.sub('<yellow>(.*?)</yellow>', colored(r"\1", EscapeCodes.YELLOW), x, flags=re.DOTALL),
    lambda x: re.sub('<green>(.*?)</green>', colored(r"\1", EscapeCodes.GREEN), x, flags=re.DOTALL),
    lambda x: re.sub('`(.*?)`', r"`\1`" if ascii_only else EscapeCodes.UNDERLINE + r"\1" + EscapeCodes.ENDC, x),
]


def fmt(*parts: str) -> str:
    result = ''.join(parts)
    for f in fmt_transformations:
        result = f(result)
    return result


def get_vertical_bar() -> str:
    return "|" if ascii_only else u"│"


def get_right_arrow() -> str:
    return "->" if ascii_only else u"➔"


def get_pretty_choices(*choices: str) -> str:
    def format_choice(c: str) -> str:
        if not c:
            return ''
        elif c.lower() == 'y':
            return colored(c, EscapeCodes.GREEN)
        elif c.lower() == 'yq':
            return colored(c[0], EscapeCodes.GREEN) + colored(c[1], EscapeCodes.RED)
        elif c.lower() in ('n', 'q'):
            return colored(c, EscapeCodes.RED)
        else:
            return colored(c, EscapeCodes.ORANGE)
    return f" ({', '.join(map_truthy_only(format_choice, choices))}) "


def debug(hdr: str, msg: str) -> None:
    if debug_mode:
        sys.stderr.write(f"{bold(hdr)}: {dim(msg)}\n")


def run_cmd(cmd: str, *args: str, **kwargs: Any) -> int:
    chdir_upwards_until_current_directory_exists()

    flat_cmd: str = get_cmd_shell_repr(cmd, *args, **kwargs)
    if debug_mode:
        sys.stderr.write(bold(f">>> {flat_cmd}") + "\n")
    elif verbose_mode:
        sys.stderr.write(flat_cmd + "\n")

    exit_code: int = subprocess.call([cmd] + list(args), **kwargs)

    # Let's defensively assume that every command executed via run_cmd
    # (but not via popen_cmd) can make the current directory disappear.
    # In practice, it's mostly 'git checkout' that carries such risk.
    mark_current_directory_as_possibly_non_existent()

    if debug_mode and exit_code != 0:
        sys.stderr.write(dim(f"<exit code: {exit_code}>\n\n"))
    return exit_code


def mark_current_directory_as_possibly_non_existent() -> None:
    global current_directory_confirmed_to_exist
    current_directory_confirmed_to_exist = False


def chdir_upwards_until_current_directory_exists() -> None:
    global current_directory_confirmed_to_exist
    if not current_directory_confirmed_to_exist:
        current_directory: Optional[str] = get_current_directory_or_none()
        if not current_directory:
            while not current_directory:
                # Note: 'os.chdir' only affects the current process and its subprocesses;
                # it doesn't propagate to the parent process (which is typically a shell).
                os.chdir(os.path.pardir)
                current_directory = get_current_directory_or_none()
            debug("chdir_upwards_until_current_directory_exists()",
                  f"current directory did not exist, chdired up into {current_directory}")
        current_directory_confirmed_to_exist = True


def popen_cmd(cmd: str, *args: str, **kwargs: Any) -> Tuple[int, str, str]:
    chdir_upwards_until_current_directory_exists()

    flat_cmd = get_cmd_shell_repr(cmd, *args, **kwargs)
    if debug_mode:
        sys.stderr.write(bold(f">>> {flat_cmd}") + "\n")
    elif verbose_mode:
        sys.stderr.write(flat_cmd + "\n")

    process = subprocess.Popen([cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    stdout_bytes, stderr_bytes = process.communicate()
    stdout: str = stdout_bytes.decode('utf-8')
    stderr: str = stderr_bytes.decode('utf-8')
    exit_code: int = process.returncode

    if debug_mode:
        if exit_code != 0:
            sys.stderr.write(colored(f"<exit code: {exit_code}>\n\n", EscapeCodes.RED))
        if stdout:
            sys.stderr.write(f"{dim('<stdout>:')}\n{dim(stdout)}\n")
        if stderr:
            sys.stderr.write(f"{dim('<stderr>:')}\n{colored(stderr, EscapeCodes.RED)}\n")

    return exit_code, stdout, stderr


def get_cmd_shell_repr(cmd: str, *args: str, **kwargs: Dict[str, str]) -> str:
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


def warn(msg: str, apply_fmt: bool = True) -> None:
    if msg not in displayed_warnings:
        sys.stderr.write(colored("Warn: ", EscapeCodes.RED) + (fmt(msg) if apply_fmt else msg) + "\n")
        displayed_warnings.add(msg)


def slurp_file_or_empty(path: str) -> str:
    try:
        with open(path, 'r') as file:
            return file.read()
    except IOError:
        return ''
