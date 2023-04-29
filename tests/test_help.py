from typing import Any, List

import pytest

from git_machete.cli import commands_and_aliases
from git_machete.exceptions import ExitCode

from .base_test import BaseTest
from .mockers import launch_command, mock_exit_script_no_exit, mock_run_cmd


class TestHelp(BaseTest):

    def test_help(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        with pytest.raises(SystemExit) as e:
            launch_command()
        assert ExitCode.ARGUMENT_ERROR == e.value.code

        with pytest.raises(SystemExit) as e:
            launch_command("help")
        assert ExitCode.SUCCESS == e.value.code

        with pytest.raises(SystemExit) as e:
            launch_command("help", "no-such-command")
        assert ExitCode.ARGUMENT_ERROR == e.value.code

        help_topics: List[str] = ['config', 'format', 'hooks']

        for command in commands_and_aliases:

            with pytest.raises(SystemExit) as e:
                launch_command("help", command)
            assert ExitCode.SUCCESS == e.value.code

            if command not in help_topics:
                with pytest.raises(SystemExit) as e:
                    launch_command(command, "--help")
                assert ExitCode.SUCCESS == e.value.code
            else:
                with pytest.raises(SystemExit) as e:
                    launch_command(command, "--help")
                assert ExitCode.ARGUMENT_ERROR == e.value.code

    def test_help_output_has_no_ansi_codes(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script_no_exit)
        for command in commands_and_aliases:
            help_output = launch_command('help', command)
            assert '\033' not in help_output
