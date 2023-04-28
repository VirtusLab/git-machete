from typing import Any

from git_machete import __version__

from .mockers import assert_command, mock_exit_script_no_exit


class TestVersion:

    def test_version(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script_no_exit)
        mocker.patch('sys.exit', mock_exit_script_no_exit)

        assert_command(
            ["version"],
            f"git-machete version {__version__}\n"
        )
