import pytest

from .mockers import (GitRepositorySandbox, get_current_commit_hash,
                      launch_command, popen)


class TestSquash:

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

    def test_squash_with_valid_fork_point(self) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit("First commit.")
                .commit("Second commit.")
        )
        fork_point = get_current_commit_hash()

        (
            self.repo_sandbox.commit("Third commit.")
                .commit("Fourth commit.")
        )

        launch_command('squash', '-f', fork_point)

        expected_branch_log = (
            "Third commit.\n"
            "Second commit.\n"
            "First commit."
        )

        current_branch_log = popen('git log -3 --format=%s')
        assert current_branch_log == \
            expected_branch_log, \
            ("Verify that `git machete squash -f <fork-point>` squashes commit"
                " from one succeeding the fork-point until tip of the branch.")

    def test_squash_with_invalid_fork_point(self) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit()
                .new_branch('branch-1a')
                .commit()
        )
        fork_point_to_branch_1a = get_current_commit_hash()

        (
            self.repo_sandbox.check_out('branch-0')
                .new_branch('branch-1b')
                .commit()
        )

        with pytest.raises(SystemExit):
            # First exception MacheteException is raised, followed by SystemExit.
            launch_command('squash', '-f', fork_point_to_branch_1a)
