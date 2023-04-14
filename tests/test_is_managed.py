import pytest

from .mockers import (GitRepositorySandbox, launch_command,
                      rewrite_definition_file)


class TestIsManaged:

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

    def test_is_managed(self) -> None:
        """
        Verify behaviour of a 'git machete is-managed' command.
        """
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
        body: str = \
            """
            master
            develop
                feature
            """
        rewrite_definition_file(body)

        # Test `git machete is-managed` without providing the branch name
        launch_command('is-managed')

        launch_command('is-managed', 'develop')

        launch_command('is-managed', 'refs/heads/develop')

        with pytest.raises(SystemExit):
            launch_command('is-managed', 'random_branch_name')
