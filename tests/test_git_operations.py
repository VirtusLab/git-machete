
from git_machete.git_operations import (AnyBranchName, AnyRevision,
                                        FullCommitHash, GitContext,
                                        LocalBranchShortName)

from .base_test import BaseTest
from .mockers import write_to_file
from .mockers_git_repository import (check_out, commit, create_repo,
                                     get_current_commit_hash,
                                     is_ancestor_or_equal, new_branch,
                                     new_orphan_branch, set_git_config_key)


class TestGitOperations(BaseTest):

    def test_run_git(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        master_branch_first_commit_hash = get_current_commit_hash()

        git = GitContext()
        assert git._run_git("rev-parse", "--verify", "--quiet",
                            master_branch_first_commit_hash + "^{commit}", allow_non_zero=True, flush_caches=False) == 0  # noqa: FS003
        assert git._run_git("rev-parse", "HEAD", flush_caches=False) == 0

    def test_popen_git(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        master_branch_first_commit_hash = get_current_commit_hash()

        new_branch("develop")
        commit("develop commit")
        new_branch("feature")
        commit("feature commit")

        git = GitContext()

        def is_commit_present_in_repository(revision: AnyRevision) -> bool:
            return git._popen_git("rev-parse", "--verify", "--quiet",
                                  revision + "^{commit}", allow_non_zero=True).exit_code == 0  # noqa: FS003

        assert is_commit_present_in_repository(revision=FullCommitHash(40 * 'a')) is False
        assert is_commit_present_in_repository(revision=AnyRevision(master_branch_first_commit_hash)) is True

        assert is_ancestor_or_equal(earlier=LocalBranchShortName('feature'),
                                    later=LocalBranchShortName('master')) is False
        assert is_ancestor_or_equal(earlier=LocalBranchShortName('develop'),
                                    later=LocalBranchShortName('feature')) is True

    def test_is_equivalent_tree_or_patch_reachable_with_squash_merge(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        new_branch("feature")
        commit("feature commit")
        check_out("master")

        git = GitContext()
        assert git._run_git("merge", "--squash", "feature", flush_caches=False) == 0
        assert git._run_git("commit", "-m", "squashed", flush_caches=False) == 0

        feature = AnyRevision("feature")
        master = AnyRevision("master")

        # Both methods should return True, as there are no commits in master before we merged feature
        assert git.is_equivalent_tree_reachable(equivalent_to=feature, reachable_from=master) is True
        assert git.is_equivalent_patch_reachable(equivalent_to=feature, reachable_from=master) is True

    def test_is_equivalent_tree_or_patch_reachable_with_squash_merge_and_commits_in_between(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        new_branch("feature")
        commit("feature commit")
        check_out("master")
        commit("extra commit")

        git = GitContext()
        assert git._run_git("merge", "--squash", "feature", flush_caches=False) == 0
        assert git._run_git("commit", "-m", "squashed", flush_caches=False) == 0

        feature = AnyRevision("feature")
        master = AnyRevision("master")

        # Here the simple method will not detect the squash merge, as there are commits in master before we merged feature so
        # there's no tree hash in master that matches the tree hash of feature
        assert git.is_equivalent_tree_reachable(equivalent_to=feature, reachable_from=master) is False
        assert git.is_equivalent_patch_reachable(equivalent_to=feature, reachable_from=master) is True

        check_out("master")
        commit("another master commit")
        git.flush_caches()  # so that the old position of `master` isn't remembered

        assert git.is_equivalent_tree_reachable(equivalent_to=feature, reachable_from=master) is False
        assert git.is_equivalent_patch_reachable(equivalent_to=feature, reachable_from=master) is True

    def test_is_equivalent_tree_or_patch_reachable_with_rebase(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        new_branch("feature")
        commit("feature commit")
        check_out("master")

        git = GitContext()
        assert git._run_git("rebase", "feature", flush_caches=False) == 0

        feature = AnyRevision("feature")
        master = AnyRevision("master")

        # Same as merge example, both methods should return True as there are no commits in master before we rebased feature
        assert git.is_equivalent_tree_reachable(equivalent_to=feature, reachable_from=master) is True
        assert git.is_equivalent_patch_reachable(equivalent_to=feature, reachable_from=master) is True

        check_out("master")
        commit("another master commit")
        git.flush_caches()  # so that the old position of `master` isn't remembered

        # Simple method fails if there are commits after the rebase, as this case is covered by the "is ancestor"
        # check in the is_merged_to method in client.py
        assert git.is_equivalent_tree_reachable(equivalent_to=feature, reachable_from=master) is False
        assert git.is_equivalent_patch_reachable(equivalent_to=feature, reachable_from=master) is True

    def test_is_equivalent_tree_or_patch_reachable_with_rebase_and_commits_in_between(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        new_branch("feature")
        commit("feature commit")
        check_out("master")
        commit("extra commit")

        git = GitContext()
        assert git._run_git("rebase", "feature", flush_caches=False) == 0

        feature = AnyRevision("feature")
        master = AnyRevision("master")

        # Same as the merge example, the simple method will not detect the rebase, as there are commits
        # in master before we rebased feature and tree hashes are always different
        assert git.is_equivalent_tree_reachable(equivalent_to=feature, reachable_from=master) is False
        assert git.is_equivalent_patch_reachable(equivalent_to=feature, reachable_from=master) is True

        check_out("master")
        commit("another master commit")
        git.flush_caches()  # so that the old position of `master` isn't remembered

        assert git.is_equivalent_tree_reachable(equivalent_to=feature, reachable_from=master) is False
        assert git.is_equivalent_patch_reachable(equivalent_to=feature, reachable_from=master) is True
        # To cover retrieval of the result from cache
        assert git.is_equivalent_patch_reachable(equivalent_to=feature, reachable_from=master) is True

    def test_is_equivalent_tree_or_patch_reachable_when_no_common_ancestor(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        new_orphan_branch("feature")
        commit("feature commit")

        git = GitContext()
        feature = AnyRevision("feature")
        master = AnyRevision("master")

        assert git.is_equivalent_tree_reachable(equivalent_to=feature, reachable_from=master) is False
        assert git.is_equivalent_patch_reachable(equivalent_to=feature, reachable_from=master) is False

    def test_git_config_with_newlines(self) -> None:
        create_repo()
        write_to_file(".git/config", '[foo]\n  bar = "hello\\nworld"')
        git = GitContext()
        assert git.get_config_attr_or_none("foo.bar") == "hello\nworld"

    def test_get_reflog_when_log_showsignature_is_true(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        new_branch("feature")
        commit("feature commit")
        check_out("master")
        commit("extra commit")
        set_git_config_key("log.showSignature", "true")

        git = GitContext()

        # If the bug reported in GitHub issue #1286 is not fixed, this method call
        # should raise an UnexpectedMacheteException.
        git.get_reflog(AnyBranchName.of("feature"))
