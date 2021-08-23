from git_machete import utils


class MacheteException(Exception):
    def __init__(self, msg: str, apply_fmt: bool = True) -> None:
        self.parameter = utils.get_fmt(msg) if apply_fmt else msg

    def __str__(self) -> str:
        return str(self.parameter)


class StopTraversal(Exception):
    def __init__(self) -> None:
        pass
