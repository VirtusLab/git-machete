import os

from git_machete.git_operations import (AnyBranchName, AnyRevision,
                                        FullCommitHash, GitContext,
                                        LocalBranchShortName)

from .base_test import BaseTest
from .mockers import write_to_file
from .mockers_git_repository import (add_worktree, check_out, commit,
                                     create_repo, get_current_commit_hash,
                                     get_git_version, is_ancestor_or_equal,
                                     new_branch, new_orphan_branch,
                                     set_git_config_key)


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

    def test_get_reflog_for_branch_with_at_sign(self) -> None:
        create_repo()
        new_branch("feature@foo")
        commit("feature commit")

        git = GitContext()
        # If the bug reported in GitHub issue #1481 is not fixed, this method call
        # should raise an UnexpectedMacheteException.
        git.get_reflog(AnyBranchName.of("feature@foo"))

    def test_get_worktree_root_dirs_by_branch(self) -> None:
        if get_git_version() < (2, 5):
            # git worktree command was introduced in git 2.5
            return

        create_repo()
        new_branch("main")
        commit("main commit")
        new_branch("feature-1")
        commit("feature-1 commit")
        new_branch("feature-2")
        commit("feature-2 commit")
        new_branch("feature-3")
        commit("feature-3 commit")

        git = GitContext()
        main_worktree_path = git.get_current_worktree_root_dir()

        # Test 1: Main worktree on a branch, no linked worktrees
        check_out("main")
        worktrees = git.get_worktree_root_dirs_by_branch()
        assert len(worktrees) == 1
        assert worktrees.get(LocalBranchShortName.of("main")) == main_worktree_path
        assert git.get_worktree_root_dirs_by_branch().get(LocalBranchShortName.of("main")) == main_worktree_path
        assert git.get_worktree_root_dirs_by_branch().get(LocalBranchShortName.of("feature-1")) is None

        # Test 2: Create linked worktrees
        feature1_worktree = add_worktree("feature-1")
        feature2_worktree = add_worktree("feature-2")

        worktrees = git.get_worktree_root_dirs_by_branch()
        assert len(worktrees) == 3
        assert worktrees.get(LocalBranchShortName.of("main")) == main_worktree_path
        # On macOS, paths may have /private prefix, so use realpath to normalize
        feature1_path = worktrees.get(LocalBranchShortName.of("feature-1"))
        assert feature1_path is not None
        assert os.path.realpath(feature1_path) == os.path.realpath(feature1_worktree)
        feature2_path = worktrees.get(LocalBranchShortName.of("feature-2"))
        assert feature2_path is not None
        assert os.path.realpath(feature2_path) == os.path.realpath(feature2_worktree)
        assert git.get_worktree_root_dirs_by_branch().get(LocalBranchShortName.of("feature-3")) is None

        # Test 3: Main worktree in detached HEAD (should NOT be in dict)
        main_commit = git.get_commit_hash_by_revision(LocalBranchShortName.of("main"))
        assert main_commit is not None
        check_out(main_commit)  # Detach HEAD in main worktree

        worktrees = git.get_worktree_root_dirs_by_branch()
        assert len(worktrees) == 2  # Only feature-1 and feature-2, not the detached main
        assert LocalBranchShortName.of("main") not in worktrees
        feature1_path = worktrees.get(LocalBranchShortName.of("feature-1"))
        assert feature1_path is not None
        assert os.path.realpath(feature1_path) == os.path.realpath(feature1_worktree)
        feature2_path = worktrees.get(LocalBranchShortName.of("feature-2"))
        assert feature2_path is not None
        assert os.path.realpath(feature2_path) == os.path.realpath(feature2_worktree)

        # Test 4: Linked worktree in detached HEAD (should NOT be in dict)
        initial_dir = os.getcwd()
        os.chdir(feature1_worktree)
        feature1_commit = git.get_commit_hash_by_revision(LocalBranchShortName.of("feature-1"))
        assert feature1_commit is not None
        check_out(feature1_commit)  # Detach HEAD in feature-1 worktree
        os.chdir(initial_dir)

        worktrees = git.get_worktree_root_dirs_by_branch()
        assert len(worktrees) == 1  # Only feature-2, not main (detached) or feature-1 (detached)
        assert LocalBranchShortName.of("main") not in worktrees
        assert LocalBranchShortName.of("feature-1") not in worktrees
        feature2_path = worktrees.get(LocalBranchShortName.of("feature-2"))
        assert feature2_path is not None
        assert os.path.realpath(feature2_path) == os.path.realpath(feature2_worktree)

        # Test 5: Create another worktree in detached HEAD to ensure they don't overwrite each other
        # This tests the bug fix where multiple detached HEADs would overwrite each other with None key
        from tempfile import mkdtemp

        from .mockers import execute
        feature3_worktree = mkdtemp()
        execute(f"git worktree add -f --detach {feature3_worktree} feature-3")

        worktrees = git.get_worktree_root_dirs_by_branch()
        # Should still be 1 (only feature-2), detached worktrees should not be included
        assert len(worktrees) == 1
        assert LocalBranchShortName.of("feature-3") not in worktrees

        # Test 6: Check out branch in the detached worktree, should now appear
        os.chdir(feature1_worktree)
        check_out("feature-1")  # Back on branch
        os.chdir(initial_dir)

        worktrees = git.get_worktree_root_dirs_by_branch()
        assert len(worktrees) == 2  # feature-1 and feature-2
        feature1_path = worktrees.get(LocalBranchShortName.of("feature-1"))
        assert feature1_path is not None
        assert os.path.realpath(feature1_path) == os.path.realpath(feature1_worktree)
        feature2_path = worktrees.get(LocalBranchShortName.of("feature-2"))
        assert feature2_path is not None
        assert os.path.realpath(feature2_path) == os.path.realpath(feature2_worktree)
