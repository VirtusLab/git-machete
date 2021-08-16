from git_machete import utils


class MacheteException(Exception):
    def __init__(self, msg: str, apply_fmt: bool = True) -> None:
        self.parameter = utils.fmt(msg) if apply_fmt else msg

    def __str__(self) -> str:
        return str(self.parameter)


class StopTraversal(Exception):
    def __init__(self) -> None:
        pass


class UnprocessableEntityHTTPError(Exception):
    """This exception is raised when Github API returns HTTP status code 422 - Unprocessable Entity.
    Such a situation occurs when trying to do something not allowed by github, egz. assign as a reviewer someone from outside organization or create a pull request which is already created.
    """
    pass
