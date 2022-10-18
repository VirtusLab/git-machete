from typing import Any, List

import pytest

from git_machete.generated_docs import long_docs

from unittest import mock

from .mockers import GitRepositorySandbox, launch_command, mock_exit_script_no_exit, mock_run_cmd


class TestHelp:

    def setup_method(self) -> None:

        self.repo_sandbox = GitRepositorySandbox()

        (
            self.repo_sandbox
            # Create the remote and sandbox repos, chdir into sandbox repo
            .new_repo(self.repo_sandbox.remote_path, "--bare")
            .new_repo(self.repo_sandbox.local_path)
            .execute(f"git remote add origin {self.repo_sandbox.remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
        )

    def test_help(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        expected_exit_code = None
        expected_exit_code_when_failed = 2
        help_topics: List[str] = ['config', 'format', 'hooks']

        with pytest.raises(SystemExit) as e:
            launch_command("help")
        assert expected_exit_code == e.value.code, \
            "Verify that `git machete help` causes SystemExit with " \
            f"{expected_exit_code} exit code."

        for command in long_docs:

            with pytest.raises(SystemExit) as e:
                launch_command("help", command)
            assert expected_exit_code == e.value.code, \
                f"Verify that `git machete help {command}` causes SystemExit" \
                f" with {expected_exit_code} exit code."

            if command not in help_topics:
                with pytest.raises(SystemExit) as e:
                    launch_command(command, "--help")
                assert expected_exit_code == e.value.code, \
                    f"Verify that `git machete {command} --help` causes " \
                    f"SystemExit with {expected_exit_code} exit code."
            else:
                with pytest.raises(SystemExit) as e:
                    launch_command(command, "--help")
                assert expected_exit_code_when_failed == e.value.code, \
                    f"Verify that `git machete {command} --help` causes " \
                    f"SystemExit with {expected_exit_code} exit code."

    @mock.patch('git_machete.cli.exit_script', mock_exit_script_no_exit)
    def test_help_output_has_no_ansi_codes(self) -> None:
        for command in long_docs.keys():
            help_output = launch_command('help', command)
            assert '\033' not in help_output
