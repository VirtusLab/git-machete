# Tutorial - Part 8: Squashing and reapplying

After updating your branch with a rebase, you might want to clean up its history before pushing it for review.
`git-machete` provides two commands to help with this: `squash` and `reapply`.

### Squashing commits

If you've made several small commits while working on a feature,
you might want to combine them into a single, clean commit by running:
```shell
git machete squash
```
`git-machete` will automatically find the fork point (start of unique history)
of your branch and squash all commits following it into one.
The commit message will be taken from the first commit in the series.

### Reapplying a branch

To re-run an interactive rebase of your current branch onto its fork point, use:
```shell
git machete reapply
```
This is useful if you want to manually pick, squash, or drop commits using the standard git interactive rebase interface.

Note that `reapply` is different from [`update`](07-updating-a-branch-with-a-rebase.md) in that it does **not** rebase onto the parent branch.
After `reapply`, the sequence of commits (potentially reworded/squashed/etc.)
will still be based on the same commit (fork point) as before.
In other words, `reapply` cleans up your branch's history without bringing in new changes from the parent.

### Fork point

Both `squash` and `reapply` rely on fork point discovery.
If the automatic discovery ever fails, you can override the fork point with the `--fork-point` flag,
similarly to how it's done in `update`:
```shell
git machete [reapply|squash] --fork-point <commit-hash>
```

[< Previous: Updating a branch with a rebase](07-updating-a-branch-with-a-rebase.md) | [Next: Automating workflow with `traverse` >](09-automating-workflow-with-traverse.md)
