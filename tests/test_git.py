import os
from tempfile import mkdtemp
from typing import Dict, Optional

import pytest

from git_machete.git import AnyBranchName, AnyRevision, FullCommitHash, Git, LocalBranchShortName
from git_machete.git_version_thresholds import WORKTREE_COMMAND
from git_machete.utils.paths import AbsPath
from tests.base_test import BaseTest
from tests.git_repository import (add_worktree, check_out, commit, create_repo, get_current_commit_hash, get_git_version,
                                  is_ancestor_or_equal, new_branch, new_orphan_branch, set_git_config_key)
from tests.shell import execute, read_file, write_to_file


class TestGitOperations(BaseTest):

    def test_run_git(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        master_branch_first_commit_hash = get_current_commit_hash()

        git = Git()
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

        git = Git()

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

        git = Git()
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

        git = Git()
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

        git = Git()
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

        git = Git()
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

        git = Git()
        feature = AnyRevision("feature")
        master = AnyRevision("master")

        assert git.is_equivalent_tree_reachable(equivalent_to=feature, reachable_from=master) is False
        assert git.is_equivalent_patch_reachable(equivalent_to=feature, reachable_from=master) is False

    def test_git_config_with_newlines(self) -> None:
        create_repo()
        write_to_file(".git/config", '[foo]\n  bar = "hello\\nworld"')
        git = Git()
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

        git = Git()

        # If the bug reported in GitHub issue #1286 is not fixed, this method call
        # should raise an UnexpectedMacheteException.
        git.get_reflog(AnyBranchName.of("feature"))

    def test_get_reflog_for_branch_with_at_sign(self) -> None:
        create_repo()
        new_branch("feature@foo")
        commit("feature commit")

        git = Git()
        # If the bug reported in GitHub issue #1481 is not fixed, this method call
        # should raise an UnexpectedMacheteException.
        git.get_reflog(AnyBranchName.of("feature@foo"))

    @pytest.mark.skipif(get_git_version() < WORKTREE_COMMAND, reason="git worktree command was introduced in git 2.5")
    def test_load_branch_by_worktree_root_dir(self) -> None:
        """Direct unit test of `Git.load_branch_by_worktree_root_dir`. Walks through every interesting
        permutation of (main vs linked) X (on-branch vs detached) and asserts the full returned dict
        each time, pinning down both the keying direction (path -> Optional[branch]) and the contract
        that detached-HEAD worktrees stay first-class entries with `value=None` rather than being
        filtered out for lack of a branch name."""
        create_repo()
        new_branch("main")
        commit("main commit")
        new_branch("feature-1")
        commit("feature-1 commit")
        new_branch("feature-2")
        commit("feature-2 commit")
        new_branch("feature-3")
        commit("feature-3 commit")

        git = Git()
        main_worktree_path = git.get_current_worktree_root_dir()

        def by_real_path(d: Dict[AbsPath, Optional[LocalBranchShortName]]) -> Dict[str, Optional[LocalBranchShortName]]:
            # macOS resolves `mkdtemp` paths under `/private/...`, so the porcelain output and the
            # `add_worktree` return value can disagree by a `/private` prefix. Normalize both sides
            # to `os.path.realpath` so each step can assert on the full mapping in one go.
            return {os.path.realpath(p): b for p, b in d.items()}

        main = LocalBranchShortName.of("main")
        feature1 = LocalBranchShortName.of("feature-1")
        feature2 = LocalBranchShortName.of("feature-2")

        # Test 1: Main worktree on a branch, no linked worktrees
        check_out("main")
        assert by_real_path(git.load_branch_by_worktree_root_dir()) == {
            os.path.realpath(main_worktree_path): main,
        }

        # Test 2: Add two linked worktrees, each on its own branch
        feature1_worktree = add_worktree("feature-1")
        feature2_worktree = add_worktree("feature-2")

        assert by_real_path(git.load_branch_by_worktree_root_dir()) == {
            os.path.realpath(main_worktree_path): main,
            os.path.realpath(feature1_worktree): feature1,
            os.path.realpath(feature2_worktree): feature2,
        }

        # Test 3: Detach HEAD in the main worktree. The entry stays in the snapshot, but with
        # `value=None` to signal "this worktree exists, but no branch is checked out here".
        main_commit = git.get_commit_hash_by_revision(main)
        assert main_commit is not None
        check_out(main_commit)

        assert by_real_path(git.load_branch_by_worktree_root_dir()) == {
            os.path.realpath(main_worktree_path): None,
            os.path.realpath(feature1_worktree): feature1,
            os.path.realpath(feature2_worktree): feature2,
        }

        # Test 4: Detach HEAD in a linked worktree too. Both detached entries coexist as distinct
        # rows - one per worktree path - rather than collapsing onto each other.
        initial_dir = os.getcwd()
        os.chdir(feature1_worktree)
        feature1_commit = git.get_commit_hash_by_revision(feature1)
        assert feature1_commit is not None
        check_out(feature1_commit)
        os.chdir(initial_dir)

        assert by_real_path(git.load_branch_by_worktree_root_dir()) == {
            os.path.realpath(main_worktree_path): None,
            os.path.realpath(feature1_worktree): None,
            os.path.realpath(feature2_worktree): feature2,
        }

        # Test 5: Add a *third* detached worktree (pointing at the `feature-3` commit but not on the
        # branch) - three coexisting `None`-value rows confirm that detached entries are addressed
        # per-worktree rather than collapsing under any shared "no branch here" key.
        feature3_worktree = mkdtemp()
        execute(f"git worktree add -f --detach {feature3_worktree} feature-3")

        assert by_real_path(git.load_branch_by_worktree_root_dir()) == {
            os.path.realpath(main_worktree_path): None,
            os.path.realpath(feature1_worktree): None,
            os.path.realpath(feature2_worktree): feature2,
            os.path.realpath(feature3_worktree): None,
        }

        # Test 6: Re-checkout `feature-1` in its (currently detached) linked worktree - the entry
        # flips from None back to the branch name without changing keys.
        os.chdir(feature1_worktree)
        check_out("feature-1")
        os.chdir(initial_dir)

        assert by_real_path(git.load_branch_by_worktree_root_dir()) == {
            os.path.realpath(main_worktree_path): None,
            os.path.realpath(feature1_worktree): feature1,
            os.path.realpath(feature2_worktree): feature2,
            os.path.realpath(feature3_worktree): None,
        }

    def test_merge_base_cache_loading_and_saving(self) -> None:
        """Test merge-base cache with various edge cases."""
        create_repo()
        new_branch("master")
        commit("master first commit")
        master_hash = FullCommitHash.of(get_current_commit_hash())
        new_branch("feature")
        commit("feature commit")
        feature_hash = FullCommitHash.of(get_current_commit_hash())
        check_out("master")
        commit("master second commit")
        master_hash2 = FullCommitHash.of(get_current_commit_hash())

        git = Git()
        cache_path = os.path.join(git.get_main_worktree_git_dir(), "machete-merge-base-cache")

        # Test 1: Cache file doesn't exist - should work normally
        assert not os.path.exists(cache_path)
        merge_base1 = git.get_merge_base(master_hash, feature_hash)
        assert merge_base1 is not None
        # Cache should now exist and contain the entry
        assert os.path.exists(cache_path)
        cache_content = read_file(cache_path)
        assert master_hash.full_name() in cache_content or feature_hash.full_name() in cache_content
        assert merge_base1.full_name() in cache_content

        # Test 2: Cache with valid entries (using fake hashes that will be loaded into cache)
        valid_hash1 = "a" * 40
        valid_hash2 = "b" * 40
        valid_merge_base = "c" * 40
        write_to_file(cache_path, f"{valid_hash1} {valid_hash2} {valid_merge_base}\n")
        git = Git()  # New instance to test cache loading
        # Access cache by calling get_merge_base (which triggers cache load)
        git.get_merge_base(master_hash, feature_hash)
        # Check that valid entry was loaded (even though these are fake hashes, they should be in cache)
        assert git._merge_base_cached is not None
        # Normalize hash order
        if valid_hash1 < valid_hash2:
            hash1_norm, hash2_norm = FullCommitHash.of(valid_hash1), FullCommitHash.of(valid_hash2)
        else:
            hash1_norm, hash2_norm = FullCommitHash.of(valid_hash2), FullCommitHash.of(valid_hash1)
        assert (hash1_norm, hash2_norm) in git._merge_base_cached
        assert git._merge_base_cached[(hash1_norm, hash2_norm)] == FullCommitHash.of(valid_merge_base)

        # Test 3: Cache with valid entry missing 3rd field (no merge-base - rare case)
        orphan_hash1 = "d" * 40
        orphan_hash2 = "e" * 40
        write_to_file(cache_path, f"{orphan_hash1} {orphan_hash2}\n")
        git = Git()
        git.get_merge_base(master_hash, feature_hash)  # Trigger cache load
        assert git._merge_base_cached is not None
        # Normalize hash order
        if orphan_hash1 < orphan_hash2:
            orphan1_norm, orphan2_norm = FullCommitHash.of(orphan_hash1), FullCommitHash.of(orphan_hash2)
        else:
            orphan1_norm, orphan2_norm = FullCommitHash.of(orphan_hash2), FullCommitHash.of(orphan_hash1)
        assert (orphan1_norm, orphan2_norm) in git._merge_base_cached
        assert git._merge_base_cached[(orphan1_norm, orphan2_norm)] is None

        # Test 4: Cache with various invalid entries - should ignore them
        invalid_entries = [
            "single_entry",  # Only 1 entry
            "hash1 hash2 hash3 hash4",  # 4+ entries
            "short1 short2 merge",  # Short hashes (not 40 chars)
            "x" * 39 + " " + "y" * 39 + " " + "z" * 39,  # 39-char hashes
            "complete gibberish with spaces and stuff",  # Gibberish
            "a" * 40 + " " + "b" * 40 + " " + "short",  # Valid hashes but short merge-base
            "a" * 40 + " " + "short" + " " + "c" * 40,  # Short hash2
            "short" + " " + "b" * 40 + " " + "c" * 40,  # Short hash1
            "nothex" + "x" * 34 + " " + "b" * 40 + " " + "c" * 40,  # Invalid hex in hash1
            "a" * 40 + " " + "nothex" + "x" * 34 + " " + "c" * 40,  # Invalid hex in hash2
            "a" * 40 + " " + "b" * 40 + " " + "nothex" + "x" * 34,  # Invalid hex in merge-base
        ]
        valid_entry = f"{valid_hash1} {valid_hash2} {valid_merge_base}"
        cache_content_with_invalid = "\n".join(invalid_entries) + "\n" + valid_entry + "\n"
        write_to_file(cache_path, cache_content_with_invalid)
        git = Git()
        git.get_merge_base(master_hash, feature_hash)  # Trigger cache load
        # Should still have the valid entry loaded
        assert git._merge_base_cached is not None
        # Normalize hash order
        if valid_hash1 < valid_hash2:
            valid1_norm, valid2_norm = FullCommitHash.of(valid_hash1), FullCommitHash.of(valid_hash2)
        else:
            valid1_norm, valid2_norm = FullCommitHash.of(valid_hash2), FullCommitHash.of(valid_hash1)
        assert (valid1_norm, valid2_norm) in git._merge_base_cached
        # Invalid entries should be ignored (not cause errors)

        # Test 5: Cache with empty lines and whitespace
        write_to_file(cache_path, f"\n  \n\t\n{valid_hash1} {valid_hash2} {valid_merge_base}\n\n")
        git = Git()
        git.get_merge_base(master_hash, feature_hash)  # Trigger cache load
        assert git._merge_base_cached is not None
        # Normalize hash order
        if valid_hash1 < valid_hash2:
            valid1_norm, valid2_norm = FullCommitHash.of(valid_hash1), FullCommitHash.of(valid_hash2)
        else:
            valid1_norm, valid2_norm = FullCommitHash.of(valid_hash2), FullCommitHash.of(valid_hash1)
        assert (valid1_norm, valid2_norm) in git._merge_base_cached

        # Test 6: Cache with hash order normalization (hash1 > hash2)
        hash_larger = "f" * 40
        hash_smaller = "a" * 40
        merge_base_normalized = "0" * 40
        write_to_file(cache_path, f"{hash_larger} {hash_smaller} {merge_base_normalized}\n")
        git = Git()
        git.get_merge_base(master_hash, feature_hash)  # Trigger cache load
        assert git._merge_base_cached is not None
        # Should be normalized to (smaller, larger)
        hash_smaller_norm = FullCommitHash.of(hash_smaller)
        hash_larger_norm = FullCommitHash.of(hash_larger)
        assert (hash_smaller_norm, hash_larger_norm) in git._merge_base_cached
        assert git._merge_base_cached[(hash_smaller_norm, hash_larger_norm)] == FullCommitHash.of(merge_base_normalized)

        # Test 7: Cache saving appends new entries and normalizes hash order
        initial_size = os.path.getsize(cache_path) if os.path.exists(cache_path) else 0
        # Compute a new merge-base that's not in cache
        new_branch("other")
        commit("other commit")
        other_hash = FullCommitHash.of(get_current_commit_hash())
        # Ensure we test with hash1 > hash2 to verify normalization on write
        if master_hash2 > other_hash:
            larger_hash, smaller_hash = master_hash2, other_hash
        else:
            larger_hash, smaller_hash = other_hash, master_hash2
        git.get_merge_base(larger_hash, smaller_hash)  # Compute merge-base to trigger cache write
        # Check that cache file grew
        assert os.path.exists(cache_path)
        new_size = os.path.getsize(cache_path)
        assert new_size > initial_size
        # Verify the new entry is in the file with normalized order (smaller <= larger)
        cache_content_after = read_file(cache_path)
        # The entry should be written as "smaller_hash larger_hash merge_base"
        # (not "larger_hash smaller_hash merge_base")
        assert f"{smaller_hash.full_name()} {larger_hash.full_name()}" in cache_content_after
        # Verify it's NOT written in reverse order
        assert f"{larger_hash.full_name()} {smaller_hash.full_name()}" not in cache_content_after

        # Test 8: Cache is used when entry exists (no git merge-base call needed)
        # We'll test this by ensuring the cached value is returned
        # First, write a cache entry for real commits
        write_to_file(cache_path, f"{master_hash.full_name()} {feature_hash.full_name()} {merge_base1.full_name()}\n")
        git2 = Git()
        # Load cache and get merge-base - should use cached value
        cached_merge_base = git2.get_merge_base(master_hash, feature_hash)
        # The result should match what we put in cache
        assert cached_merge_base == merge_base1
        # Verify it's in the cache dict
        assert git2._merge_base_cached is not None
        # Normalize hash order for lookup
        hash1_norm, hash2_norm = (master_hash, feature_hash) if master_hash < feature_hash else (feature_hash, master_hash)
        assert git2._merge_base_cached is not None  # Help mypy understand it's not None
        cached_result = git2._merge_base_cached.get((hash1_norm, hash2_norm))
        assert cached_result == merge_base1
