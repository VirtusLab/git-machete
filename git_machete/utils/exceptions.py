"""Exception types and small enums shared across `git_machete`.

`MacheteException` and `UnderlyingGitException` route their messages through
`_fmt` so callers can use the markup language (e.g. `<b>`, `<red>`)
inside the message and have it rendered consistently with the rest of the
output.
"""

from enum import Enum, IntEnum
from typing import Optional, Type, TypeVar

from .markup import _fmt

# Parent-package imports are intentionally lazy (inside function bodies); see
# `markup.py` for the rationale.

E = TypeVar('E', bound=Enum)

NEW_ISSUE_LINK = "https://github.com/VirtusLab/git-machete/issues/new"


class InteractionStopped(Exception):
    def __init__(self) -> None:
        pass


class UnderlyingGitException(Exception):
    def __init__(self, msg: str) -> None:
        from git_machete import utils as _utils

        self.msg: str = _fmt(msg, use_ansi_escapes=_utils.use_ansi_escapes_in_stdout)

    def __str__(self) -> str:
        return str(self.msg)


class MacheteException(Exception):
    def __init__(self, msg: str) -> None:
        from git_machete import utils as _utils

        self.msg: str = _fmt(msg, use_ansi_escapes=_utils.use_ansi_escapes_in_stdout)

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
