import datetime
import inspect
import os
import re
import subprocess
import sys
import textwrap
import time
from enum import Enum, IntEnum
from pathlib import Path, PurePosixPath
from typing import (Any, Callable, Dict, Iterable, List, NamedTuple, Optional,
                    Sequence, Set, Tuple, Type, TypeVar)

T = TypeVar('T')
U = TypeVar('U')
E = TypeVar('E', bound=Enum)


# To avoid displaying the same warning multiple times during a single run.
displayed_warnings: Set[str] = set()

# Let's keep the flag to avoid checking for current directory's existence
# every time any command is being popened or run.
current_directory_confirmed_to_exist: bool = False

use_ansi_escapes_in_stdout: bool = sys.stdout.isatty()
use_ansi_escapes_in_stderr: bool = sys.stderr.isatty()
debug_mode: bool = False
measure_command_time: bool = os.environ.get('GIT_MACHETE_MEASURE_COMMAND_TIME') == 'true'  # undocumented, internal
verbose_mode: bool = False

# https://github.blog/2021-04-05-behind-githubs-new-authentication-token-formats/
# https://docs.gitlab.com/ee/security/token_overview.html#gitlab-tokens
CODE_HOSTING_TOKEN_PREFIXES = ['ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_', 'glpat-']
CODE_HOSTING_TOKEN_PREFIX_REGEX = '(' + '|'.join(CODE_HOSTING_TOKEN_PREFIXES) + ')'


# === TTY / terminal detection ===

def is_stdout_a_tty() -> bool:
    return sys.stdout.isatty()


def is_stderr_a_tty() -> bool:
    return sys.stderr.isatty()


def get_terminal_height() -> Optional[int]:
    """
    Get the height (number of lines) of the terminal.
    Returns None if terminal size cannot be determined (e.g., not a TTY).
    """
    try:
        return os.get_terminal_size().lines
    except (OSError, AttributeError):
        return None


_terminal_fully_fledged: Optional[bool] = None


def is_terminal_fully_fledged() -> bool:
    global _terminal_fully_fledged
    if _terminal_fully_fledged is None:
        try:
            stdout = popen_cmd('tput', 'colors')[1]
            # In CI, this line is only covered by tests on macOS, which don't run on PRs by default.
            # Let's skip to keep coverage results consistent between develop/master and PRs.
            number_of_supported_colors = int(stdout)  # pragma: no cover
        except Exception:
            # If we cannot retrieve the number of supported colors, let's defensively assume it's low.
            number_of_supported_colors = 8
        _terminal_fully_fledged = number_of_supported_colors >= 256
    return _terminal_fully_fledged


def hex_repr(input: str) -> str:
    # Skip the first two `0x` characters.
    return ':'.join(hex(ord(char))[2:] for char in input)


# === ANSI escape code classes ===

class AnsiInputCodes:
    """Fixed escape sequences for reading keyboard input.

    These are standard VT100/xterm codes and are not affected by terminal
    capabilities (color depth, etc.).
    """
    ESCAPE = '\033'
    CSI = '\033['  # Control Sequence Introducer

    KEY_UP = '\033[A'
    KEY_DOWN = '\033[B'
    KEY_RIGHT = '\033[C'
    KEY_LEFT = '\033[D'
    KEY_SHIFT_UP = '\033[1;2A'
    KEY_SHIFT_DOWN = '\033[1;2B'

    KEYS_ENTER = ('\r', '\n')
    KEY_SPACE = ' '
    KEY_CTRL_C = '\003'


class FullTerminalAnsiOutputCodes:
    CSI = '\033['  # Control Sequence Introducer

    # Text styling
    ENDC = '\033[0m'
    ENDC_UNDERLINE = '\033[24m'
    ENDC_BOLD_DIM = '\033[22m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    ORANGE = '\033[00;38;5;208m'
    RED = '\033[91m'
    REVERSE_VIDEO = '\033[7m'

    # Cursor control
    HIDE_CURSOR = '\033[?25l'
    SHOW_CURSOR = '\033[?25h'
    CLEAR_TO_END = '\033[J'

    def cursor_up(self, num_lines: int) -> str:
        """CSI n A — move cursor up by num_lines."""
        return self.CSI + str(num_lines) + "A"


class BasicTerminalAnsiOutputCodes(FullTerminalAnsiOutputCodes):
    """Output codes adapted to the 8-bit terminal's capabilities."""

    UNDERLINE = '\033[36m'  # cyan
    ENDC_UNDERLINE = FullTerminalAnsiOutputCodes.ENDC
    ORANGE = FullTerminalAnsiOutputCodes.YELLOW
    RED = '\033[31m'  # dark red


# === Markup formatting ===

def escape_markup(s: str) -> str:
    """Escape characters that `_fmt` would interpret as markup.

    Use on user-provided content (annotation text, commit subjects, hook
    output) before embedding it into markup strings.
    """
    return s.replace('&', '&amp;').replace('`', '&backtick;').replace('<', '&lt;')


def _fmt(s: str, *, use_ansi_escapes: bool) -> str:

    # `GIT_MACHETE_DIM_AS_GRAY` remains undocumented as for now,
    # is just needed for animated gifs to render correctly
    # (`[2m`-style dimmed text is invisible in asciicinema renders).
    __dim_as_gray = os.environ.get('GIT_MACHETE_DIM_AS_GRAY') == 'true'
    dim = '\033[38;2;128;128;128m' if __dim_as_gray else '\033[2m'

    ao = FullTerminalAnsiOutputCodes() if is_terminal_fully_fledged() else BasicTerminalAnsiOutputCodes()

    # pattern                                ansi replacement                            ascii replacement
    rules: List[Tuple[str, str, str]] = [
        ('`(.*?)`',                         f'{ao.UNDERLINE}\\1{ao.ENDC_UNDERLINE}',    r'\1'),              # noqa: E241
        ('<b>(.*?)</b>',                    f'{ao.BOLD}\\1{ao.ENDC_BOLD_DIM}',          r'\1'),              # noqa: E241
        ('<u>(.*?)</u>',                    f'{ao.UNDERLINE}\\1{ao.ENDC_UNDERLINE}',    r'\1'),              # noqa: E241
        ('<dim>(.*?)</dim>',                f'{dim}\\1{ao.ENDC_BOLD_DIM}',              r'\1'),              # noqa: E241
        ('<gray>(.*?)</gray>',              f'{dim}\\1{ao.ENDC_BOLD_DIM}',              r'\1'),              # noqa: E241
        ('<red>(.*?)</red>',                f'{ao.RED}\\1{ao.ENDC}',                    r'\1'),              # noqa: E241
        ('<yellow>(.*?)</yellow>',          f'{ao.YELLOW}\\1{ao.ENDC}',                 r'\1'),              # noqa: E241
        ('<green>(.*?)</green>',            f'{ao.GREEN}\\1{ao.ENDC}',                  r'\1'),              # noqa: E241
        ('<orange>(.*?)</orange>',          f'{ao.ORANGE}\\1{ao.ENDC}',                 r'\1'),              # noqa: E241
        ('<reverse>(.*?)</reverse>',        f'{ao.REVERSE_VIDEO}\\1{ao.ENDC}',          r'\1'),              # noqa: E241
        ('<vbar/>',                          '│',                                        '|'),               # noqa: E241
        ('<rarrow/>',                        '➔',                                        '->'),              # noqa: E241
        (r'<ifansi:([^:]*):([^/]*)/>',      r'\1',                                      r'\2'),              # noqa: E241
        ('&backtick;',                       '`',                                        '`'),               # noqa: E241
        ('&lt;',                             '<',                                        '<'),               # noqa: E241
        ('&amp;',                            '&',                                        '&'),               # noqa: E241
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
    use_ansi = use_ansi_escapes_in_stderr if file is sys.stderr else use_ansi_escapes_in_stdout
    # Defaults to stdout at call time so that contextlib.redirect_stdout is respected.
    if file is None:
        file = sys.stdout
    content = _fmt(s, use_ansi_escapes=use_ansi)
    print(content, file=file, end='\n' if newline else '', flush=not newline)


def input_fmt(prompt: str) -> str:
    return input(_fmt(prompt, use_ansi_escapes=use_ansi_escapes_in_stdout))


def warn(msg: str, *, extra_newline: bool = False) -> None:
    if msg not in displayed_warnings:
        line = f"<orange>Warn: </orange>{msg}"
        if extra_newline:
            line += "\n"
        print_fmt(line, file=sys.stderr)
        displayed_warnings.add(msg)


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


# === Path utilities ===

def join_paths_posix(*paths: str) -> str:
    """
    Join path components using forward slashes (POSIX-style), regardless of platform.

    This ensures consistent path representation across all platforms, matching
    how Git itself represents paths. Forward slashes work in all Windows
    environments (Git Bash, PowerShell, CMD) and are the standard on Unix-like systems.
    """
    return str(PurePosixPath(*paths))


def abspath_posix(path: str) -> str:
    """
    Return an absolute path using POSIX-style forward slashes.

    This ensures consistent path representation across all platforms, matching
    how Git itself represents paths.
    """
    return Path(path).resolve().as_posix()


def relpath_posix(path: str) -> str:
    """
    Return a relative filepath to path from the CWD, using POSIX-style forward slashes.

    This ensures consistent path representation across all platforms, matching
    how Git itself represents paths.
    """
    rel = os.path.relpath(path)
    return Path(rel).as_posix()


# === Generic collection / iteration utilities ===

def excluding(iterable: Iterable[T], s: Iterable[T]) -> List[T]:
    return list(filter(lambda x: x not in s, iterable))


def flat_map(func: Callable[[T], List[T]], iterable: Iterable[T]) -> List[T]:
    return sum(map(func, iterable), [])


def find_or_none(func: Callable[[T], bool], iterable: Iterable[T]) -> Optional[T]:
    return next(filter(func, iterable), None)  # type: ignore [arg-type]


def index_or_none(seq: Sequence[T], value: T) -> Optional[int]:
    try:
        return seq.index(value)
    except ValueError:
        return None


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


# === File system utilities ===

def does_directory_exist(path: str) -> bool:
    try:
        # Note that os.path.isdir itself (without os.path.abspath) isn't reliable
        # since it returns a false positive (True) for the current directory when it doesn't exist
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


def slurp_file(path: str) -> str:
    with open(path, 'r') as file:
        return file.read()


def get_current_date() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


# === Debug / logging ===

def compact_dict(d: Dict[str, Any]) -> Dict[str, str]:
    return {k: re.sub('\n +', ' ', str(v)) for k, v in d.items()}


def debug(msg: str) -> None:
    if not debug_mode:
        return

    func = inspect.stack()[1].function
    args, _, _, values_original = inspect.getargvalues(inspect.stack()[1].frame)
    # Do not write over the original values!
    # Since Python 3.13, the result of `getargvalues` keeps a map of local variables
    # that the Python runtime actually keeps on the stack,
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


# === Command execution ===

def _run_cmd(cmd: str, *args: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> int:
    # capture_output argument is only supported since Python 3.7
    return subprocess.run([cmd] + list(args), stdout=None, stderr=None, cwd=cwd, env=env).returncode


def run_cmd(cmd: str, *args: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> int:
    chdir_upwards_until_current_directory_exists()

    flat_cmd: str = get_cmd_shell_repr(cmd, *args, env=env)
    escaped_flat_cmd = escape_markup(flat_cmd)

    def print_command(markup: str) -> None:
        if measure_command_time:  # pragma: no cover
            print_fmt(markup + " ... ", file=sys.stderr, newline=False)
        else:
            print_fmt(markup, file=sys.stderr)

    if debug_mode:
        print_command(f"<b>>>> {escaped_flat_cmd}</b>")
    elif verbose_mode or measure_command_time:
        print_command(escaped_flat_cmd)

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
        print_fmt(f"<dim>&lt;exit code: {exit_code}>\n</dim>", file=sys.stderr)
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
    escaped_flat_cmd = escape_markup(flat_cmd)

    def print_command(markup: str) -> None:
        if measure_command_time:  # pragma: no cover
            print_fmt(markup + " ... ", file=sys.stderr, newline=False)
        else:
            print_fmt(markup, file=sys.stderr)

    if debug_mode:
        print_command(f"<b>>>> {escaped_flat_cmd}</b>")
    elif verbose_mode or measure_command_time:
        print_command(escaped_flat_cmd)

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
            print_fmt(f"<red>&lt;exit code: {exit_code}>\n</red>", file=sys.stderr)
        if stdout:
            if hide_debug_output:
                print_fmt("<dim>&lt;stdout>:</dim>\n<dim>&lt;REDACTED></dim>", file=sys.stderr)
            else:
                print_fmt(f"<dim>&lt;stdout>:</dim>\n<dim>{escape_markup(stdout)}</dim>", file=sys.stderr)
        if stderr:
            if hide_debug_output:
                print_fmt("<dim>&lt;stderr>:</dim>\n<dim>&lt;REDACTED></dim>", file=sys.stderr)
            else:
                print_fmt(f"<dim>&lt;stderr>:</dim>\n<red>{escape_markup(stderr)}</red>", file=sys.stderr)

    return result


def get_cmd_shell_repr(cmd: str, *args: str, env: Optional[Dict[str, str]]) -> str:
    def shell_escape(arg: str) -> str:
        return re.sub("[() <>$]", r"\\\g<0>", arg) \
            .replace("\t", "$'\\t'") \
            .replace("\n", "$'\\n'")

    env = env if env is not None else {}
    # We don't want to include the env vars that are inherited from the environment of git-machete process
    env_repr = [k + "=" + shell_escape(v) for k, v in env.items() if k not in os.environ]
    return " ".join(env_repr + [cmd] + [shell_escape(arg) for arg in args])


# === Exceptions and enums ===

NEW_ISSUE_LINK = "https://github.com/VirtusLab/git-machete/issues/new"


class InteractionStopped(Exception):
    def __init__(self) -> None:
        pass


class UnderlyingGitException(Exception):
    def __init__(self, msg: str) -> None:
        self.msg: str = _fmt(msg, use_ansi_escapes=use_ansi_escapes_in_stdout)

    def __str__(self) -> str:
        return str(self.msg)


class MacheteException(Exception):
    def __init__(self, msg: str) -> None:
        self.msg: str = _fmt(msg, use_ansi_escapes=use_ansi_escapes_in_stdout)

    def __str__(self) -> str:
        return str(self.msg)


class UnexpectedMacheteException(MacheteException):
    def __init__(self, msg: str) -> None:
        super().__init__(f"{msg}\n\nConsider posting an issue at `{NEW_ISSUE_LINK}`")


class ExitCode(IntEnum):
    SUCCESS = 0
    MACHETE_EXCEPTION = 1
    ARGUMENT_ERROR = 2
    KEYBOARD_INTERRUPT = 3
    END_OF_FILE_SIGNAL = 4


class ParsableEnum(Enum):
    @classmethod
    def from_string(cls: Type[E], value: str, from_where: Optional[str]) -> E:
        try:
            return cls[value.upper().replace("-", "_")]
        except KeyError:
            valid_values = ', '.join('`' + e.name.lower().replace("_", "-") + '`' for e in cls)
            prefix = f"Invalid value for {from_where}" if from_where else "Invalid value"
            printed_value = value or '<empty>'
            raise MacheteException(f"{prefix}: `{printed_value}`. Valid values are {valid_values}")


class CommandResult(NamedTuple):
    stdout: str
    stderr: str
    exit_code: int
