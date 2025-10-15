import os
from typing import List

from git_machete.client.base import MacheteClient
from git_machete.exceptions import MacheteException
from git_machete.git_operations import (AnyRevision, FullCommitHash,
                                        GitFormatPatterns, GitLogEntry,
                                        LocalBranchShortName)
from git_machete.utils import bold, fmt


class SquashMacheteClient(MacheteClient):
    def squash(self, *, current_branch: LocalBranchShortName, opt_fork_point: AnyRevision) -> None:
        self._git.expect_no_operation_in_progress()

        commits: List[GitLogEntry] = self._git.get_commits_between(earliest_exclusive=opt_fork_point, latest_inclusive=current_branch)
        if not commits:
            raise MacheteException(
                "No commits to squash. Use `-f` or `--fork-point` to specify the "
                "start of range of commits to squash.")
        if len(commits) == 1:
            print(f"Exactly one commit ({bold(commits[0].short_hash)}) to squash, ignoring.")
            print(fmt("Tip: use `-f` or `--fork-point` to specify where the range of commits to squash starts."))
            return

        earliest_commit = commits[0]
        earliest_full_message = self._git.get_commit_data(FullCommitHash.of(earliest_commit.hash), GitFormatPatterns.FULL_MESSAGE).strip()
        earliest_author_date = self._git.get_commit_data(FullCommitHash.of(earliest_commit.hash),
                                                         GitFormatPatterns.AUTHOR_DATE).strip()
        earliest_author_email = self._git.get_commit_data(FullCommitHash.of(earliest_commit.hash),
                                                          GitFormatPatterns.AUTHOR_EMAIL).strip()
        earliest_author_name = self._git.get_commit_data(FullCommitHash.of(earliest_commit.hash),
                                                         GitFormatPatterns.AUTHOR_NAME).strip()

        # Following the convention of `git cherry-pick`, `git commit --amend`, `git rebase` etc.,
        # let's retain the original author (only committer will be overwritten).
        author_env = dict(os.environ,
                          GIT_AUTHOR_DATE=earliest_author_date,
                          GIT_AUTHOR_EMAIL=earliest_author_email,
                          GIT_AUTHOR_NAME=earliest_author_name)
        # Using `git commit-tree` since it's cleaner than any high-level command
        # like `git merge --squash` or `git rebase --interactive`.
        # The tree (HEAD^{tree}) argument must be passed as first,
        # otherwise the entire `commit-tree` will fail on some ancient supported
        # versions of git (at least on v1.7.10).
        squashed_hash = FullCommitHash.of(self._git.commit_tree_with_given_parent_and_message_and_env(
            opt_fork_point, earliest_full_message, author_env).strip())

        # This can't be done with `git reset` since it doesn't allow for a custom reflog message.
        # Even worse, reset's reflog message would be filtered out in our fork point algorithm,
        # so the squashed commit would not even be considered to "belong"
        # (in the fork-point sense) to the current branch's history.
        self._git.update_head_ref_to_new_hash_with_reflog_subject(
            squashed_hash, f"squash: {earliest_commit.subject}")

        print(f"Squashed {len(commits)} commits:")
        print()
        for commit in commits:
            print(f"    {commit.short_hash} {commit.subject}")

        print()
        print("To restore the original pre-squash commit, run:")
        print()
        print(fmt(f"    `git reset {commits[-1].hash}`"))
