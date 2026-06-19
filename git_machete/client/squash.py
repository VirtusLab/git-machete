import os
from typing import List, Optional

from git_machete.client.base import MacheteClient
from git_machete.git import AnyRevision, FullCommitHash, GitFormatPatterns, GitLogEntry
from git_machete.utils.exceptions import MacheteException
from git_machete.utils.markup import print_fmt


class SquashMacheteClient(MacheteClient):
    def squash(self, *, opt_fork_point: Optional[AnyRevision]) -> None:
        self._git.expect_no_operation_in_progress()
        current_branch = self._git.get_current_branch()
        if opt_fork_point is not None:
            self.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                fork_point=opt_fork_point, branch=current_branch)
        fork_point = opt_fork_point or self.fork_point_or_none(branch=current_branch, use_overrides=True)
        if fork_point is None:
            raise MacheteException(
                f"git-machete cannot determine the range of commits unique to branch <b>{current_branch}</b>.\n"
                f"Use `git machete squash --fork-point=...` to select the commit "
                f"after which the commits of <b>{current_branch}</b> start.\n"
                "For example, if you want to squash 3 latest commits, use `git machete squash --fork-point=HEAD~3`."
            )

        commits: List[GitLogEntry] = self._git.get_commits_between(earliest_exclusive=fork_point, latest_inclusive=current_branch)
        if not commits:
            raise MacheteException(
                "No commits to squash. Use `-f` or `--fork-point` to specify the "
                "start of range of commits to squash.")
        if len(commits) == 1:
            print_fmt(f"Exactly one commit (<b>{commits[0].short_hash}</b>) to squash, ignoring.")
            print_fmt("Tip: use `-f` or `--fork-point` to specify where the range of commits to squash starts.")
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
        # Using `git commit-tree` since it's cleaner than any high-level command like `git merge --squash` or `git rebase --interactive`.
        # The tree (HEAD^{tree}) argument must be passed as first,
        # otherwise the entire `commit-tree` will fail on some ancient supported versions of git (at least on v1.7.10).
        squashed_hash = FullCommitHash.of(self._git.commit_tree_with_given_parent_and_message_and_env(
            fork_point, earliest_full_message, author_env).strip())

        # This can't be done with `git reset` since it doesn't allow for a custom reflog message.
        # Even worse, reset's reflog message would be filtered out in our fork point algorithm,
        # so the squashed commit would not even be considered to "belong" (in the fork-point sense) to the current branch's history.
        self._git.update_head_ref_to_new_hash_with_reflog_subject(
            squashed_hash, f"squash: {earliest_commit.subject}")

        print(f"Squashed {len(commits)} commits:")
        print()
        for commit in commits:
            print(f"    {commit.short_hash} {commit.subject}")

        print()
        print("To restore the original pre-squash commit, run:")
        print()
        print_fmt(f"    `git reset {commits[-1].hash}`")
