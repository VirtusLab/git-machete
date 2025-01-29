
from .base_test import BaseTest, GitRepositorySandbox
from .mockers import (assert_failure, assert_success,
                      fixed_author_and_committer_date_in_past, launch_command,
                      overridden_environment)


class TestSquash(BaseTest):

    def test_squash_root_branch(self) -> None:
        GitRepositorySandbox().new_branch("master").commit().commit()

        assert_failure(
            ["squash"],
            "git-machete cannot determine the range of commits unique to branch master.\n"
            "Use git machete squash --fork-point=... to select the commit after which the commits of master start.\n"
            "For example, if you want to squash 3 latest commits, use git machete squash --fork-point=HEAD~3."
        )

    def test_squash_no_commits(self) -> None:
        GitRepositorySandbox().new_branch("master").commit().new_branch("develop")

        assert_failure(
            ["squash"],
            "No commits to squash. Use -f or --fork-point to specify the "
            "start of range of commits to squash."
        )

    def test_squash_single_commit(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        with fixed_author_and_committer_date_in_past():
            (
                repo_sandbox
                .new_branch("master")
                .commit()
                .new_branch("develop")
                .commit()
            )

        assert_success(
            ["squash"],
            "Exactly one commit (dcd2db5) to squash, ignoring.\n"
            "Tip: use -f or --fork-point to specify where the range of commits to squash starts.\n"
        )

    def test_squash_with_valid_fork_point(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        repo_sandbox.new_branch('branch-0').commit("First commit.").commit("Second commit.")
        fork_point = repo_sandbox.get_current_commit_hash()

        with overridden_environment(GIT_AUTHOR_EMAIL="another@test.com"):
            repo_sandbox.commit("Third commit.")
        repo_sandbox.commit("Fourth commit.")

        launch_command('squash', '-f', fork_point)

        expected_branch_log = (
            "Third commit.\n"
            "Second commit.\n"
            "First commit."
        )

        current_branch_log = repo_sandbox.popen('git log -3 --format=%s')
        assert current_branch_log == expected_branch_log, \
            ("Verify that `git machete squash -f <fork-point>` squashes commit"
             " from one succeeding the fork-point until tip of the branch.")

        squash_commit_author = repo_sandbox.popen('git log -1 --format=%aE')
        assert squash_commit_author == "another@test.com"
        squash_commit_committer = repo_sandbox.popen('git log -1 --format=%cE')
        assert squash_commit_committer == "tester@test.com"

    def test_squash_with_invalid_fork_point(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        with fixed_author_and_committer_date_in_past():
            (
                repo_sandbox.new_branch('branch-0')
                .commit()
                .new_branch('branch-1a')
                .commit()
            )
            fork_point_to_branch_1a = repo_sandbox.get_current_commit_hash()

            (
                repo_sandbox.check_out('branch-0')
                .new_branch('branch-1b')
                .commit()
            )

        assert_failure(
            ['squash', '-f', fork_point_to_branch_1a],
            "Fork point dcd2db55125a1b67b367565e890a604639949a51 is not ancestor of or the tip of the branch-1b branch."
        )
