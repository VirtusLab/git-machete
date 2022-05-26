from typing import Any

from .mockers import (GitRepositorySandbox, assert_command, launch_command, mock_run_cmd)


class TestAdd:

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

    def test_add(self, mocker: Any) -> None:
        """
        Verify behaviour of a 'git machete add' command.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("master")
                .commit("master commit.")
                .new_branch("develop")
                .commit("develop commit.")
                .new_branch("feature")
                .commit("feature commit.")
                .check_out("develop")
                .commit("New commit on develop")
        )
        launch_command("discover", "-y")

        self.repo_sandbox.new_branch("bugfix/feature_fail")

        # Test `git machete add` without providing the branch name
        assert_command(
            ['add', '-y'],
            'Adding `bugfix/feature_fail` onto the inferred upstream (parent) branch `develop`\n'
            'Added branch `bugfix/feature_fail` onto `develop`\n',
            strip_indentation=False
        )

        self.repo_sandbox.check_out('develop')
        self.repo_sandbox.new_branch("bugfix/some_feature")
        assert_command(
            ['add', '-y', 'bugfix/some_feature'],
            'Adding `bugfix/some_feature` onto the inferred upstream (parent) branch `develop`\n'
            'Added branch `bugfix/some_feature` onto `develop`\n',
            strip_indentation=False
        )

        self.repo_sandbox.check_out('develop')
        self.repo_sandbox.new_branch("bugfix/another_feature")
        assert_command(
            ['add', '-y', 'refs/heads/bugfix/another_feature'],
            'Adding `bugfix/another_feature` onto the inferred upstream (parent) branch `develop`\n'
            'Added branch `bugfix/another_feature` onto `develop`\n',
            strip_indentation=False
        )

        # test with --onto option
        self.repo_sandbox.new_branch("chore/remove_indentation")

        assert_command(
            ['add', '--onto=feature'],
            'Added branch `chore/remove_indentation` onto `feature`\n',
            strip_indentation=False
        )
