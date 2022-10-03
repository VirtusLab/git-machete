from git_operations import FullCommitHash, GitContext, LocalBranchShortName
from .mockers import (get_current_commit_hash, GitRepositorySandbox)


class TestGitOperations:

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

    def test_run_git(self) -> None:
        """
        Verify behaviour of a 'GitContext._run_git()' method via `GitContext.is_commit_present_in_repository()` method
        """
        (
            self.repo_sandbox.new_branch("master")
                .commit('Master commit')
        )
        existing_commit_hash = get_current_commit_hash()
        git = GitContext()
        assert git.is_commit_present_in_repository(revision=FullCommitHash(40 * 'a')) is False
        assert git.is_commit_present_in_repository(revision=existing_commit_hash) is True

    def test_popen_git(self) -> None:
        """
        Verify behaviour of a 'GitContext._popen_git()' method via `GitContext.is_ancestor_or_equal()` method
        """
        (
            self.repo_sandbox.new_branch("master")
                .commit('Master commit')
                .new_branch("develop")
                .commit("develop commit.")
                .new_branch("feature")
                .commit('feature commit.')
        )
        git = GitContext()
        assert git.is_ancestor_or_equal(earlier_revision=LocalBranchShortName('feature'),
                                        later_revision=LocalBranchShortName('master')) is False
        assert git.is_ancestor_or_equal(earlier_revision=LocalBranchShortName('develop'),
                                        later_revision=LocalBranchShortName('feature')) is True
