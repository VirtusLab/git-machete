
from git_machete import __version__

from .cli_runner import assert_success


class TestVersion:

    def test_version(self) -> None:
        assert_success(
            ["version"],
            f"git-machete version {__version__}\n"
        )

    def test_version_flag(self) -> None:
        # `--version` should be honoured as a top-level flag too, equivalently
        # to `git machete version`.
        assert_success(
            ["--version"],
            f"git-machete version {__version__}\n"
        )
