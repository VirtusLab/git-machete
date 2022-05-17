from typing import Any

from .mockers import (GitRepositorySandbox, assert_command, launch_command,
                      mock_run_cmd)


class TestDiff:

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

    def test_diff(self, mocker: Any) -> None:
        """
        Verify behaviour of a 'git machete add' command.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("master")
                .commit()
                .new_branch("develop")
                .commit()
        )
        launch_command("discover", "-y")
        launch_command("diff", "develop")

        # assert_command(
        #     ['add', '-y', 'bugfix/feature_fail'],
        #     'Adding `bugfix/feature_fail` onto the inferred upstream (parent) branch `develop`\n'
        #     'Added branch `bugfix/feature_fail` onto `develop`\n',
        #     strip_indentation=False
        # )
