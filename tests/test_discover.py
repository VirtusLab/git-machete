from textwrap import dedent

from .mockers import (GitRepositorySandbox, assert_command, launch_command,
                      rewrite_definition_file)


class TestDiscover:

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

    def test_discover(self) -> None:
        (
            self.repo_sandbox
                .new_branch('master')
                .commit()
                .push()
                .new_branch('feature1')
                .commit()
                .new_branch('feature2')
                .commit()
                .check_out("master")
                .new_branch('feature3')
                .commit()
                .push()
                .new_branch('feature4')
                .commit()
        )

        body: str = \
            """
            master
            feature1
            feature2 annotation
            feature3 annotation rebase=no push=no
            """
        body = dedent(body)

        rewrite_definition_file(body)
        launch_command('discover', '-y')
        expected_status_output = (
            """
            master
            |
            o-feature1 (untracked)
            | |
            | o-feature2 (untracked)
            |
            o-feature3  rebase=no push=no
              |
              o-feature4 * (untracked)
            """
        )
        assert_command(['status'], expected_status_output)
