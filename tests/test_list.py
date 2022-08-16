from typing import Any

from .mockers import (GitRepositorySandbox, assert_command, launch_command, mock_run_cmd)


class TestList:

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

    def test_list(self, mocker: Any) -> None:
        """
        Verify behaviour of a 'git machete list' command.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("master")
                .commit("master commit.")
                .new_branch("develop")
                .commit("develop commit.")
                .new_branch("feature_0")
                .commit("feature_0 commit.")
                .new_branch("feature_0_0")
                .commit("feature_0_0 commit.")
                .new_branch("feature_0_0_0")
                .commit("feature_0_0_0 commit.")
                .check_out("feature_0")
                .new_branch("feature_0_1")
                .commit("feature_0_1 commit.")
                .check_out("develop")
                .new_branch("feature_1")
                .commit("feature_1 commit.")
        )
        launch_command("discover", "-y")

        # content of the machete definition file:
        """
        master
        develop
            feature_0
                feature_0_0
                    feature_0_0_0
                feature_0_1
            feature_1
        """

        (
            self.repo_sandbox.check_out("develop")
                             .new_branch("feature_2")
                             .commit("feature_2 commit.")
        )

        expected_output = """
        master
        develop
        feature_0
        feature_0_0
        feature_0_0_0
        feature_0_1
        feature_1
        """
        assert_command(
            ['list', 'managed'],
            expected_output,
            indent=''
        )

        expected_output = """
        feature_2
        """
        assert_command(
            ['list', 'addable'],
            expected_output,
            indent=''
        )

        expected_output = """
        master
        feature_0_0_0
        feature_0_1
        feature_1
        """
        assert_command(
            ['list', 'childless'],
            expected_output,
            indent=''
        )

        expected_output = """
        feature_0
        feature_0_0
        feature_0_0_0
        feature_0_1
        feature_1
        """
        assert_command(
            ['list', 'slidable'],
            expected_output,
            indent=''
        )

        expected_output = """
        feature_0_0_0
        """
        assert_command(
            ['list', 'slidable-after', 'feature_0_0'],
            expected_output,
            indent=''
        )

        expected_output = """
        feature_2
        """
        assert_command(
            ['list', 'unmanaged'],
            expected_output,
            indent=''
        )

        self.repo_sandbox.check_out("feature_1")
        launch_command('fork-point', '--override-to-inferred')

        expected_output = """
        feature_1
        """
        assert_command(
            ['list', 'with-overridden-fork-point'],
            expected_output,
            indent=''
        )
