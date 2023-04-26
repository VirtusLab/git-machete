from typing import Any

from git_machete.git_operations import (AnyRevision, FullCommitHash,
                                        LocalBranchShortName)

from .base_test import BaseTest, git
from .mockers import get_current_commit_hash, mock_run_cmd


class TestGitOperations(BaseTest):

    def test_run_git(self, mocker: Any) -> None:
        """
        Verify behaviour of a 'GitContext._run_git()' method
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)
        (
            self.repo_sandbox.new_branch("master")
                .commit("master first commit")
        )
        master_branch_first_commit_hash = get_current_commit_hash()

        assert git._run_git("rev-parse", "--verify", "--quiet", master_branch_first_commit_hash + "^{commit}", allow_non_zero=True) == 0  # noqa: FS003, E501
        assert git._run_git("rev-parse", "HEAD") == 0

    def test_popen_git(self) -> None:
        """
        Verify behaviour of a 'GitContext._popen_git()' method
        """
        (
            self.repo_sandbox.new_branch("master")
                .commit("master first commit")
        )
        master_branch_first_commit_hash = get_current_commit_hash()
        (
            self.repo_sandbox.new_branch("develop")
                .commit("develop commit")
                .new_branch("feature")
                .commit("feature commit")
        )

        def is_commit_present_in_repository(revision: AnyRevision) -> bool:
            return git._popen_git("rev-parse", "--verify", "--quiet", revision + "^{commit}", allow_non_zero=True).exit_code == 0  # noqa: FS003, E501

        assert is_commit_present_in_repository(revision=FullCommitHash(40 * 'a')) is False
        assert is_commit_present_in_repository(revision=master_branch_first_commit_hash) is True

        assert git.is_ancestor_or_equal(earlier_revision=LocalBranchShortName('feature'),
                                        later_revision=LocalBranchShortName('master')) is False
        assert git.is_ancestor_or_equal(earlier_revision=LocalBranchShortName('develop'),
                                        later_revision=LocalBranchShortName('feature')) is True
