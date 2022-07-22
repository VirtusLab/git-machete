from git_machete import utils


class MacheteException(Exception):
    def __init__(self, msg: str, apply_fmt: bool = True) -> None:
        self.parameter: str = utils.fmt(msg) if apply_fmt else msg

    def __str__(self) -> str:
        return str(self.parameter)


class StopInteraction(Exception):
    def __init__(self) -> None:
        pass


class UnprocessableEntityHTTPError(MacheteException):
    """This exception is raised when GitHub API returns HTTP status code 422 - Unprocessable Entity.
    Such a situation occurs when trying to do something not allowed by GitHub,
    e.g. assigning someone from outside organization as a reviewer
    or creating a pull request for a branch that already has a PR.
    """

    def __init__(self, msg: str) -> None:
        self.msg: str = msg

    def __str__(self) -> str:
        return str(self.msg)
