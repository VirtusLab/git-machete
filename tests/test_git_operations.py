
from git_machete.git_operations import (AnyRevision, FullCommitHash,
                                        GitContext, LocalBranchShortName)

from .base_test import BaseTest


class TestGitOperations(BaseTest):

    def test_run_git(self) -> None:
        (
            self.repo_sandbox.new_branch("master")
                .commit("master first commit")
        )
        master_branch_first_commit_hash = self.repo_sandbox.get_current_commit_hash()

        git = GitContext()
        assert git._run_git("rev-parse", "--verify", "--quiet",
                            master_branch_first_commit_hash + "^{commit}", allow_non_zero=True, flush_caches=False) == 0  # noqa: FS003
        assert git._run_git("rev-parse", "HEAD", flush_caches=False) == 0

    def test_popen_git(self) -> None:
        (
            self.repo_sandbox.new_branch("master")
                .commit("master first commit")
        )
        master_branch_first_commit_hash = self.repo_sandbox.get_current_commit_hash()
        (
            self.repo_sandbox.new_branch("develop")
                .commit("develop commit")
                .new_branch("feature")
                .commit("feature commit")
        )

        git = GitContext()

        def is_commit_present_in_repository(revision: AnyRevision) -> bool:
            return git._popen_git("rev-parse", "--verify", "--quiet",
                                  revision + "^{commit}", allow_non_zero=True).exit_code == 0  # noqa: FS003

        assert is_commit_present_in_repository(revision=FullCommitHash(40 * 'a')) is False
        assert is_commit_present_in_repository(revision=AnyRevision(master_branch_first_commit_hash)) is True

        assert self.repo_sandbox.is_ancestor_or_equal(earlier=LocalBranchShortName('feature'),
                                                      later=LocalBranchShortName('master')) is False
        assert self.repo_sandbox.is_ancestor_or_equal(earlier=LocalBranchShortName('develop'),
                                                      later=LocalBranchShortName('feature')) is True
