# Tutorial - Part 8: Squashing and reapplying

After updating your branch with a rebase, you might want to clean up its history before pushing it for review.
`git-machete` provides two commands to help with this: `squash` and `reapply`.

### Squashing commits

If you've made several small commits while working on a feature, you might want to combine them into a single, clean commit by running:
```shell
git machete squash
```
`git-machete` will automatically find the fork point of your branch and squash all commits following it into one.
The commit message will be taken from the first commit in the series.

### Reapplying a branch

To re-run an interactive rebase of your current branch onto its fork point, use:
```shell
git machete reapply
```
This is useful if:
* You want to manually pick, squash, or drop commits using the standard git interactive rebase interface.
* You've cherry-picked some commits from the branch elsewhere and want `git-machete` to automatically drop the duplicates.

### Fork point mechanism

Both `squash` and `reapply` rely on git-machete's **fork point** discovery.
It's an algorithm that determines where your branch actually started, even if the parent branch has been rebased or moved.
If the automatic discovery ever fails, you can override it:
```shell
git machete fork-point --override-to <commit-hash>
```

Next, we'll see how to automate the sync process for your entire branch tree.

[< Previous: Updating a branch with a rebase](07-updating-a-branch-with-a-rebase.md) | [Next: Automating workflow with traverse >](09-automating-workflow-with-traverse.md)
