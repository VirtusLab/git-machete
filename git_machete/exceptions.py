from enum import IntEnum

from git_machete import utils

NEW_ISSUE_LINK = "https://github.com/VirtusLab/git-machete/issues/new"


class InteractionStopped(Exception):
    def __init__(self) -> None:
        pass


class UnderlyingGitException(Exception):
    def __init__(self, msg: str, apply_fmt: bool = True) -> None:
        self.msg: str = utils.fmt(msg) if apply_fmt else msg

    def __str__(self) -> str:
        return str(self.msg)


class MacheteException(Exception):
    def __init__(self, msg: str, apply_fmt: bool = True) -> None:
        self.msg: str = utils.fmt(msg) if apply_fmt else msg

    def __str__(self) -> str:
        return str(self.msg)


class UnexpectedMacheteException(MacheteException):
    def __init__(self, msg: str, apply_fmt: bool = True) -> None:
        super().__init__(f"{msg}\n\nConsider posting an issue at `{NEW_ISSUE_LINK}`", apply_fmt=apply_fmt)


class ExitCode(IntEnum):
    SUCCESS = 0
    MACHETE_EXCEPTION = 1
    ARGUMENT_ERROR = 2
    KEYBOARD_INTERRUPT = 3
    END_OF_FILE_SIGNAL = 4
