import datetime
import inspect
import os
import re
import subprocess
import sys
import time
from typing import (Any, Callable, Dict, Iterable, List, NamedTuple, Optional,
                    Set, Tuple, TypeVar)

T = TypeVar('T')
U = TypeVar('U')

# To avoid displaying the same warning multiple times during a single run.
displayed_warnings: Set[str] = set()

# Let's keep the flag to avoid checking for current directory's existence
# every time any command is being popened or run.
current_directory_confirmed_to_exist: bool = False

ascii_only: bool = not sys.stdout.isatty()
debug_mode: bool = False
measure_command_time: bool = os.environ.get('GIT_MACHETE_MEASURE_COMMAND_TIME') == 'true'  # undocumented, internal
verbose_mode: bool = False

# https://github.blog/2021-04-05-behind-githubs-new-authentication-token-formats/
# https://docs.gitlab.com/ee/security/token_overview.html#gitlab-tokens
CODE_HOSTING_TOKEN_PREFIXES = ['ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_', 'glpat-']
CODE_HOSTING_TOKEN_PREFIX_REGEX = '(' + '|'.join(CODE_HOSTING_TOKEN_PREFIXES) + ')'


def excluding(iterable: Iterable[T], s: Iterable[T]) -> List[T]:
    return list(filter(lambda x: x not in s, iterable))


def flat_map(func: Callable[[T], List[T]], iterable: Iterable[T]) -> List[T]:
    return sum(map(func, iterable), [])


def find_or_none(func: Callable[[T], bool], iterable: Iterable[T]) -> Optional[T]:
    return next(filter(func, iterable), None)  # type: ignore [arg-type]


def map_truthy_only(func: Callable[[T], Optional[U]], iterable: Iterable[T]) -> List[U]:
    return list(filter(None, map(func, iterable)))


def get_non_empty_lines(s: str) -> List[str]:
    return list(filter(None, s.splitlines()))


# Converts a lambda accepting N arguments to a lambda accepting one argument, an N-element tuple.
# Name matching Scala's `tupled` on `FunctionX`.
def tupled(f: Callable[..., T]) -> Callable[[Any], T]:
    return lambda tple: f(*tple)


def get_second(pair: Tuple[Any, T]) -> T:
    _, b = pair
    return b


def does_directory_exist(path: str) -> bool:
    try:
        # Note that os.path.isdir itself (without os.path.abspath) isn't reliable
        # since it returns a false positive (True) for the current directory when if it doesn't exist
        return os.path.isdir(os.path.abspath(path))
    except OSError:  # pragma: no cover
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
        executable += ".exe"  # pragma: no cover; we don't collect coverage on Windows due to poor performance

    if os.path.isfile(executable) and is_executable(executable):
        return executable

    path = os.environ.get('PATH', os.defpath)
    paths = path.split(os.pathsep)
    for p in paths:
        f = os.path.join(p, executable)
        if os.path.isfile(f) and is_executable(f):
            debug(f"found {executable} at {f}")
            return f
    return None


def compact_dict(d: Dict[str, Any]) -> Dict[str, str]:
    return {k: re.sub('\n +', ' ', str(v)) for k, v in d.items()}


def debug(msg: str) -> None:
    if debug_mode:
        function_name = bold(inspect.stack()[1].function)
        args, _, _, values = inspect.getargvalues(inspect.stack()[1].frame)

        args_to_be_redacted = {'access_token', 'password', 'secret', 'token'}
        for arg, value in values.items():
            if arg in args_to_be_redacted or any(value_ in str(value) for value_ in CODE_HOSTING_TOKEN_PREFIXES):
                values[arg] = '***'
            if type(values[arg]) is dict:
                values[arg] = compact_dict(values[arg])

        args_and_values_list = [arg + '=' + str(values[arg]) for arg in excluding(args, {'self'})]
        args_and_values_str = ', '.join(args_and_values_list)
        args_and_values_bold_str = bold(f'({args_and_values_str})')

        print(f"{function_name}{args_and_values_bold_str}: {dim(msg)}", file=sys.stderr)


def _run_cmd(cmd: str, *args: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> int:
    # capture_output argument is only supported since Python 3.7
    return subprocess.run([cmd] + list(args), stdout=None, stderr=None, cwd=cwd, env=env).returncode


def run_cmd(cmd: str, *args: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> int:
    chdir_upwards_until_current_directory_exists()

    flat_cmd: str = get_cmd_shell_repr(cmd, *args, env=env)

    def print_command(cmd: str) -> None:
        if measure_command_time:  # pragma: no cover
            print(cmd + " ... ", file=sys.stderr, end='', flush=True)
        else:
            print(cmd, file=sys.stderr)

    if debug_mode:
        print_command(bold(f">>> {flat_cmd}"))
    elif verbose_mode or measure_command_time:
        print_command(flat_cmd)

    start = time.time()
    exit_code: int = _run_cmd(cmd, *args, cwd=cwd, env=env)
    if measure_command_time:  # pragma: no cover
        end = time.time()
        elapsed_ms = int((end - start) * 1e3)
        print(f"{elapsed_ms} ms")

    # Let's defensively assume that every command executed via run_cmd
    # (but not via popen_cmd) can make the current directory disappear.
    # In practice, it's mostly 'git checkout' that carries such risk.
    mark_current_directory_as_possibly_non_existent()

    if debug_mode and exit_code != 0:
        print(dim(f"<exit code: {exit_code}>\n"), file=sys.stderr)
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
            debug(f"current directory did not exist, chdired up into {current_directory}")
        current_directory_confirmed_to_exist = True


class PopenResult(NamedTuple):
    exit_code: int
    stdout: str
    stderr: str


def _popen_cmd(cmd: str, *args: str,
               cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None, input: Optional[str] = None) -> PopenResult:
    stdin = subprocess.PIPE if input is not None else None
    input_bytes = input.encode('utf-8') if input else None

    # capture_output argument is only supported since Python 3.7
    process = subprocess.Popen([cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=stdin, cwd=cwd, env=env)
    stdout_bytes, stderr_bytes = process.communicate(input_bytes)
    exit_code: int = process.returncode  # must be retrieved after process.communicate()
    stdout: str = stdout_bytes.decode('utf-8')
    stderr: str = stderr_bytes.decode('utf-8')
    return PopenResult(exit_code, stdout, stderr)


def popen_cmd(cmd: str, *args: str, cwd: Optional[str] = None,
              env: Optional[Dict[str, str]] = None, hide_debug_output: bool = False, input: Optional[str] = None) -> PopenResult:
    chdir_upwards_until_current_directory_exists()

    flat_cmd = get_cmd_shell_repr(cmd, *args, env=env)

    def print_command(cmd: str) -> None:
        if measure_command_time:  # pragma: no cover
            print(cmd + " ... ", file=sys.stderr, end='', flush=True)
        else:
            print(cmd, file=sys.stderr)

    if debug_mode:
        print_command(bold(f">>> {flat_cmd}"))
    elif verbose_mode or measure_command_time:
        print_command(flat_cmd)

    start = time.time()
    exit_code, stdout, stderr = result = _popen_cmd(cmd, *args, cwd=cwd, env=env, input=input)
    if measure_command_time:  # pragma: no cover
        end = time.time()
        elapsed_ms = int((end - start) * 1e3)
        print(f"{elapsed_ms} ms")

    # GitHub tokens are likely to appear e.g. in the output of `git config -l`:
    # `https://<TOKEN>@github.com/org/repo.git` is a supported URL format for git remotes.
    def redact_tokens(input: str) -> str:
        return re.sub(CODE_HOSTING_TOKEN_PREFIX_REGEX + '[a-zA-Z0-9]+', '<REDACTED>', input)
    stdout = redact_tokens(stdout)
    stderr = redact_tokens(stderr)

    if debug_mode:
        if exit_code != 0:
            print(colored(f"<exit code: {exit_code}>\n", AnsiEscapeCodes.RED), file=sys.stderr)
        if stdout:
            if hide_debug_output:
                print(f"{dim('<stdout>:')}\n{dim('<REDACTED>')}", file=sys.stderr)
            else:
                print(f"{dim('<stdout>:')}\n{dim(stdout)}", file=sys.stderr)
        if stderr:
            if hide_debug_output:
                print(f"{dim('<stderr>:')}\n{dim('<REDACTED>')}", file=sys.stderr)
            else:
                print(f"{dim('<stderr>:')}\n{colored(stderr, AnsiEscapeCodes.RED)}", file=sys.stderr)

    return result


def get_cmd_shell_repr(cmd: str, *args: str, env: Optional[Dict[str, str]]) -> str:
    def shell_escape(arg: str) -> str:
        return arg.replace("(", "\\(") \
            .replace(")", "\\)") \
            .replace(" ", "\\ ") \
            .replace("\t", "$'\\t'") \
            .replace("\n", "$'\\n'")

    env = env if env is not None else {}
    # We don't want to include the env vars that are inherited from the environment of git-machete process
    env_repr = [k + "=" + shell_escape(v) for k, v in env.items() if k not in os.environ]
    return " ".join(env_repr + [cmd] + list(map(shell_escape, args)))


def warn(msg: str, apply_fmt: bool = True, end: str = '\n') -> None:
    if msg not in displayed_warnings:
        print(colored("Warn: ", AnsiEscapeCodes.ORANGE) + (fmt(msg) if apply_fmt else msg), file=sys.stderr, end=end)
        displayed_warnings.add(msg)


def slurp_file(path: str) -> str:
    with open(path, 'r') as file:
        return file.read()


def is_terminal_fully_fledged() -> bool:
    try:
        stdout = popen_cmd('tput', 'colors')[1]
        number_of_supported_colors = int(stdout)
    except Exception:
        # If we cannot retrieve the number of supported colors, let's defensively assume it's low.
        number_of_supported_colors = 8
    return number_of_supported_colors >= 256


def hex_repr(input: str) -> str:
    # Skip the first two `0x` characters.
    return ':'.join(hex(ord(char))[2:] for char in input)


class AnsiEscapeCodes:

    __is_terminal_fully_fledged = is_terminal_fully_fledged()

    # `GIT_MACHETE_DIM_AS_GRAY` remains undocumented as for now,
    # is just needed for animated gifs to render correctly
    # (`[2m`-style dimmed text is invisible in asciicinema renders).
    __dim_as_gray = os.environ.get('GIT_MACHETE_DIM_AS_GRAY') == 'true'

    ENDC = '\033[0m'
    ENDC_UNDERLINE = '\033[24m'
    ENDC_BOLD_DIM = '\033[22m'
    BOLD = '\033[1m'
    DIM = '\033[38;2;128;128;128m' if __dim_as_gray else '\033[2m'
    # Let's fall back to cyan on 8-color terminals
    UNDERLINE = '\033[4m' if __is_terminal_fully_fledged else '\033[36m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    # Let's fall back to yellow on 8-color terminals
    ORANGE = '\033[00;38;5;208m' if __is_terminal_fully_fledged else '\033[33m'
    # Let's fall back to dark red (which might be similar to yellow :/) on 8-color terminals
    RED = '\033[91m' if __is_terminal_fully_fledged else '\033[31m'


def bold(s: str) -> str:
    return s if ascii_only or not s else AnsiEscapeCodes.BOLD + s + AnsiEscapeCodes.ENDC_BOLD_DIM


def dim(s: str) -> str:
    return s if ascii_only or not s else AnsiEscapeCodes.DIM + s + AnsiEscapeCodes.ENDC_BOLD_DIM


def underline(s: str, star_if_ascii_only: bool = False) -> str:
    if s and not ascii_only:
        return AnsiEscapeCodes.UNDERLINE + s + AnsiEscapeCodes.ENDC_UNDERLINE
    elif s and star_if_ascii_only:
        return s + " *"
    else:
        return s


def colored(s: str, color: str) -> str:
    return s if ascii_only or not s else color + s + AnsiEscapeCodes.ENDC


fmt_transformations: List[Callable[[str], str]] = [
    lambda x: re.sub('`(.*?)`', underline(r"\1"), x),
    lambda x: re.sub('<b>(.*?)</b>', bold(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<u>(.*?)</u>', underline(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<dim>(.*?)</dim>', dim(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<red>(.*?)</red>', colored(r"\1", AnsiEscapeCodes.RED), x, flags=re.DOTALL),
    lambda x: re.sub('<yellow>(.*?)</yellow>', colored(r"\1", AnsiEscapeCodes.YELLOW), x, flags=re.DOTALL),
    lambda x: re.sub('<green>(.*?)</green>', colored(r"\1", AnsiEscapeCodes.GREEN), x, flags=re.DOTALL),
    lambda x: re.sub('<orange>(.*?)</orange>', colored(r"\1", AnsiEscapeCodes.ORANGE), x, flags=re.DOTALL)
]


def fmt(*parts: str) -> str:
    result = ''.join(parts)
    for f in fmt_transformations:
        result = f(result)
    return result


def get_vertical_bar() -> str:
    return "|" if ascii_only else "│"


def get_right_arrow() -> str:
    return "->" if ascii_only else "➔"


def get_pretty_choices(*choices: str) -> str:
    def format_choice(c: str) -> str:
        if not c:
            return ''
        elif c.lower() == 'y':
            return colored(c, AnsiEscapeCodes.GREEN)
        elif c.lower() == 'yq':
            return colored(c[0], AnsiEscapeCodes.GREEN) + colored(c[1], AnsiEscapeCodes.RED)
        elif c.lower() in ('n', 'q'):
            return colored(c, AnsiEscapeCodes.RED)
        else:
            return colored(c, AnsiEscapeCodes.ORANGE)

    return f" ({', '.join(map_truthy_only(format_choice, choices))}) "


def get_current_date() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


class CommandResult(NamedTuple):
    stdout: str
    stderr: str
    exit_code: int
