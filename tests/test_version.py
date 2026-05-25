
from git_machete import __version__
from tests.cli_runner import assert_success


class TestVersion:

    def test_version(self) -> None:
        assert_success(
            ["version"],
            f"git-machete version {__version__}\n"
        )

    def test_version_flag(self) -> None:
        # `--version` should be honored as a top-level flag too, equivalently to `git machete version`.
        assert_success(
            ["--version"],
            f"git-machete version {__version__}\n"
        )
