from typing import Dict

long_docs: Dict[str, str] = {
    "traverse": """
        <b>Usage:</b> git machete t[raverse][-F|--fetch][-l|--list-commits][-M|--merge][-n|--no-edit-merge|--no-interactive-rebase][--no-detect-squash-merges][--[no-]push][--[no-]push-untracked][--return-to=WHERE][--start-from=WHERE][-w|--whole][-W][-y|--yes]

        Traverses the branch tree in pre-order (i.e. simply in the order as they occur in the definition file).
        By default `traverse` starts from the current branch.
        This behaviour can, however, be customized using options: `--start-from=` , `--whole` or `-w` , `-W` .

        For each branch, the command:

           * detects if the branch is merged ( [2mgrey[0m edge) to its parent (aka upstream):
              - by commit equivalency (default), or by strict detection of merge commits (if `--no-detect-squash-merges` passed),
              - if so, asks the user whether to slide out the branch from the dependency tree (typically branches are no longer needed after they're merged);

           * otherwise, if the branch has a [31mred[0m or [33myellow[0m edge to its parent/upstream (see status ):
              - asks the user whether to rebase (default) or merge (if `--merge` passed) the branch onto into its upstream branch
        --- equivalent to `git machete update` with no `--fork-point` option passed;

           * if the branch is not tracked on a remote, is ahead of its remote counterpart, or diverged from the counterpart & has newer head commit than the counterpart:
              - asks the user whether to push the branch (possibly with `--force-with-lease` if the branches diverged);

           * otherwise, if the branch diverged from the remote counterpart & has older head commit than the counterpart:
              - asks the user whether to `git reset --keep` the branch to its remote counterpart

           * otherwise, if the branch is behind its remote counterpart:
              - asks the user whether to pull the branch;

           * and finally, if any of the above operations has been successfully completed:
              - prints the updated `status` .

        If the traverse flow is stopped (typically due to merge/rebase conflicts), just run `git machete traverse` after the merge/rebase is finished.
        It will pick up the walk from the current branch (unless `--start-from=` or `-w` etc. is passed).
        Unlike with e.g. `git rebase` , there is no special `--continue` flag, as `traverse` is stateless
        (doesn't keep a state of its own like `git rebase` does in `.git/rebase-apply/` ).

        <b>Options:</b>
           -F,--fetchFetch the remotes of all managed branches at the beginning of traversal (no `git pull` involved, only `git fetch` ).
           -l,--list-commitsWhen printing the status, additionally list the messages of commits introduced on each branch.
           -M,--mergeUpdate by merge rather than by rebase.
           -nIf updating by rebase, equivalent to `--no-interactive-rebase` . If updating by merge, equivalent to `--no-edit-merge` .
           --no-detect-squash-mergesOnly considerstrict(fast-forward or 2-parent) merges, rather than rebase/squash merges, when detecting if a branch is merged into its upstream (parent).
           --no-edit-mergeIf updating by merge, skip opening the editor for merge commit message while doing `git merge` (i.e. pass `--no-edit` flag to the underlying `git merge` ). Not allowed if updating by rebase.
           --no-interactive-rebaseIf updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag). Not allowed if updating by merge.
           --no-pushDo not push any (neither tracked nor untracked) branches to remote, re-enable via `--push` .
           --no-push-untrackedDo not push untracked branches to remote, re-enable via `--push-untracked` .
           --pushPush all (both tracked and untracked) branches to remote --- default behavior.
           --push-untrackedPush untracked branches to remote --- default behavior.
           --return-to=WHERESpecifies the branch to return after traversal is successfully completed; WHERE can be `here` (the current branch at the moment when traversal starts), `nearest-remaining` (nearest remaining branch in case the `here` branch has been slid out by the traversal) or `stay` (the default --- just stay wherever the traversal stops). Note: when user quits by `q` / `yq` or when traversal is stopped because one of git actions fails, the behavior is always `stay` .
           --start-from=WHERESpecifies the branch to start the traversal from; WHERE can be `here` (the default --- current branch, must be managed by git machete), `root` (root branch of the current branch, as in `git machete show root` ) or `first-root` (first listed managed branch).
           -w,--wholeEquivalent to `-n --start-from=first-root --return-to=nearest-remaining` ; useful for quickly traversing & syncing all branches (rather than doing more fine-grained operations on the local section of the branch tree).
           -WEquivalent to `--fetch --whole` ; useful for even more automated traversal of all branches.
           -y,--yesDon't ask for any interactive input, including confirmation of rebase/push/pull. Implies `-n` .

        <b>Environment variables:</b>
            `GIT_MACHETE_REBASE_OPTS` 
               Extra options to pass to the underlying `git rebase` invocations, space-separated.

        Example: `GIT_MACHETE_REBASE_OPTS="--keep-empty --rebase-merges" git machete traverse` .
   """,
}
