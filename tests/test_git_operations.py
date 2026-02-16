import os

from git_machete.git_operations import (AnyBranchName, AnyRevision,
                                        FullCommitHash, GitContext,
                                        LocalBranchShortName)

from .base_test import BaseTest
from .mockers import read_file, write_to_file
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

        git = GitContext()
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
        git = GitContext()  # New instance to test cache loading
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
        git = GitContext()
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
        git = GitContext()
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
        git = GitContext()
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
        git = GitContext()
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
        git2 = GitContext()
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
