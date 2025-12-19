# Tutorial - Part 6: Updating a branch

When `git machete status` shows a branch with a **red edge**, it means the branch is out of sync with its parent.

### The update command

To sync the current branch with its parent, simply run:
```shell
git machete update
```

By default, this command performs a `rebase` of the current branch onto its parent branch (as defined in `.git/machete`).

### Fork-point mechanism

A key feature of `git-machete` is its ability to find the correct "fork-point".

If you've ever manually rebased a branch that was already rebased before, you might have encountered "re-applying commits" that were already there.
`git-machete` avoids this by tracking where a branch was originally forked from its parent, even if the parent has moved or the child has been rebased.

### Benefits of update

* No need to remember parents — `git-machete` knows exactly what to rebase onto.
* Safe — it uses the fork-point to ensure only the commits unique to your branch are rebased.
* Simple — just one command to keep your feature branch up to date with `develop` or its parent feature branch.

What if you have a whole chain of branches to update? That's where `traverse` comes in.

[< Previous: Navigating between branches](05-navigating-between-branches.md) | [Next: Automating workflow with traverse >](07-automating-workflow-with-traverse.md)
