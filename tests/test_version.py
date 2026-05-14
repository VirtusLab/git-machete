
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
        # to `git machete version`. argparse used to wire this up via a
        # `version=...` action; the hand-rolled parser handles it as a
        # short-circuit in `launch_internal`.
        assert_success(
            ["--version"],
            f"git-machete version {__version__}\n"
        )
