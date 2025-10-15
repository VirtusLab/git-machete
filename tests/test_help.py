from typing import List

from git_machete.cli import commands_and_aliases
from git_machete.exceptions import ExitCode

from .base_test import BaseTest
from .mockers import (launch_command,
                      launch_command_capturing_output_and_exception)
from .mockers_git_repository import create_repo, set_git_config_key


class TestHelp(BaseTest):

    def test_help(self) -> None:
        output, e = launch_command_capturing_output_and_exception()
        assert output and "Quick start tip" in output
        assert type(e) is SystemExit
        assert e.code == ExitCode.ARGUMENT_ERROR

        assert "--verbose" in launch_command("help")

        output, e = launch_command_capturing_output_and_exception("help", "no-such-command")
        assert type(e) is SystemExit
        assert e.code == ExitCode.ARGUMENT_ERROR

        help_topics: List[str] = ['config', 'format', 'hooks']

        for command in commands_and_aliases:

            launch_command("help", command)

            if command not in help_topics:
                output, e = launch_command_capturing_output_and_exception(command, "--help")
                assert output is not None
                assert "Usage:" in output
                assert type(e) is SystemExit
                assert e.code == ExitCode.SUCCESS
            else:
                output, e = launch_command_capturing_output_and_exception(command, "--help")
                assert type(e) is SystemExit
                assert e.code == ExitCode.ARGUMENT_ERROR

    def test_help_output_has_no_ansi_codes(self) -> None:
        for command in commands_and_aliases:
            help_output = launch_command('help', command)
            assert '\033' not in help_output

    def test_help_succeeds_despite_invalid_git_config_key(self) -> None:
        create_repo()
        set_git_config_key("machete.squashMergeDetection", "invalid")
        help_output = launch_command('help')
        assert "Usage:" in help_output
