from typing import List

import pytest

from git_machete.cli import commands_and_aliases
from git_machete.exceptions import ExitCode

from .base_test import BaseTest
from .mockers import launch_command


class TestHelp(BaseTest):

    def test_help(self) -> None:
        with pytest.raises(SystemExit) as e:
            launch_command()
        assert ExitCode.ARGUMENT_ERROR == e.value.code

        launch_command("help")

        with pytest.raises(SystemExit) as e:
            launch_command("help", "no-such-command")
        assert ExitCode.ARGUMENT_ERROR == e.value.code

        help_topics: List[str] = ['config', 'format', 'hooks']

        for command in commands_and_aliases:

            launch_command("help", command)

            if command not in help_topics:
                with pytest.raises(SystemExit) as e:
                    launch_command(command, "--help")
                assert ExitCode.SUCCESS == e.value.code
            else:
                with pytest.raises(SystemExit) as e:
                    launch_command(command, "--help")
                assert ExitCode.ARGUMENT_ERROR == e.value.code

    def test_help_output_has_no_ansi_codes(self) -> None:
        for command in commands_and_aliases:
            help_output = launch_command('help', command)
            assert '\033' not in help_output
