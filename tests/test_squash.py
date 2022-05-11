from typing import Any

import pytest

from .mockers import (GitRepositorySandbox, assert_command,
                      get_current_commit_hash, launch_command, mock_run_cmd,
                      popen)


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

    def test_squash_merge(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("root")
            .commit("root")
            .push()
            .new_branch("develop")
            .commit("develop")
            .push()
            .new_branch("feature")
            .commit("feature_1")
            .commit("feature_2")
            .push()
            .new_branch("child")
            .commit("child_1")
            .commit("child_2")
            .push()
        )

        launch_command("discover", "-y", "--roots=root")

        assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            o-develop
              |
              | feature_1
              | feature_2
              o-feature
                |
                | child_1
                | child_2
                o-child *
            """,
        )

        # squash-merge feature onto develop
        (
            self.repo_sandbox.check_out("develop")
            .execute("git merge --squash feature")
            .execute("git commit -m squash_feature")
            .check_out("child")
        )

        # in default mode, feature is detected as "m" (merged) into develop
        assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop (ahead of origin)
              |
              m-feature
                |
                | child_1
                | child_2
                o-child *
            """,
        )

        # but under --no-detect-squash-merges, feature is detected as "x" (behind) develop
        assert_command(
            ["status", "-l", "--no-detect-squash-merges"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop (ahead of origin)
              |
              | feature_1
              | feature_2
              x-feature
                |
                | child_1
                | child_2
                o-child *
            """,
        )

        # traverse then slides out the branch
        launch_command("traverse", "-w", "-y")
        assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop
              |
              | child_1
              | child_2
              o-child *
            """,
        )

        # simulate an upstream squash-merge of the feature branch
        (
            self.repo_sandbox.check_out("develop")
            .new_branch("upstream_squash")
            .execute("git merge --squash child")
            .execute("git commit -m squash_child")
            .execute("git push origin upstream_squash:develop")
            .check_out("child")
            .execute("git branch -D upstream_squash")
        )

        # status before fetch will show develop as out of date
        assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop (behind origin)
              |
              | child_1
              | child_2
              o-child *
            """,
        )

        # fetch-traverse will fetch upstream squash, detect, and slide out the child branch
        launch_command("traverse", "-W", "-y")

        assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            | squash_child
            o-develop *
            """,
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
