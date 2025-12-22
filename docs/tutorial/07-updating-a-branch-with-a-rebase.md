# Tutorial - Part 7: Updating a branch with a rebase

When `git machete status` shows a branch with a **red edge**, it means the branch is out of sync with its parent.

### The `update` command

To sync the current branch with its parent, run:
```shell
git machete update
```

This command performs a rebase of the current branch onto its parent branch (as defined in `.git/machete`).

### Fork point mechanism

A key feature of `git-machete` is its ability to find the correct fork point.
It's an algorithm that determines where your branch actually started, even if the parent branch has been rebased or moved.

If you've ever manually rebased a branch that was already rebased before,
you might have encountered "reapplying commits" that were already there.
`git-machete` avoids this by tracking the fork point of each branch —
even if the parent has changed over time, or the branch has been previously rebased.

If the automatic discovery ever fails, you can override it with the `--fork-point` flag:
```shell
git machete update --fork-point <commit-hash>
```

### Benefits of `update`

As compared to a vanilla `git rebase`:

* No need to remember parents — `git-machete` knows exactly what to rebase onto.
* Safe — it uses the fork point to ensure only the commits unique to your branch are rebased.
* Simple — one command to keep your feature branch up to date with `develop` or its parent branch.

[< Previous: Navigating between branches](06-navigating-between-branches.md) | [Next: Squashing and reapplying >](08-squashing-and-reapplying.md)
