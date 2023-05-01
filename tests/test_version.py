
from git_machete import __version__

from .mockers import assert_success


class TestVersion:

    def test_version(self) -> None:
        assert_success(
            ["version"],
            f"git-machete version {__version__}\n"
        )
