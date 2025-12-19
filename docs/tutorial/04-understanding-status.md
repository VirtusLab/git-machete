# Tutorial - Part 4: Understanding status

The most frequently used command in `git-machete` is:
```shell
git machete status
```
It provides a "bird's eye view" of your repository.

### Color-coded status

When you run `status`, you'll see your branch tree with colored edges (the lines connecting branches):

* Green — the branch is in sync with its parent.
  All commits from the parent are already present in the child branch.
* Red — the branch is out of sync.
  The parent has commits that are not yet in the child branch.
  This branch can be rebased onto its parent.
* Gray — the branch is merged into its parent.
  It can be safely "slid out" (more on that later).
* Yellow — the branch is in sync with its parent, but its remote tracking branch has different commits.
  You might need to push or pull.

### Listing commits

To see exactly what's on each branch, use:
```shell
git machete status --list-commits
```
(or `git machete s -l` for short).

This will list the commits that are unique to each branch.
It's a great way to quickly remind yourself what you were working on in each feature branch.

### Example output

```text
  master
  |
  o-develop (ahead of origin)
    |
    | m-feature-1 (merged into develop)
    |
    o-feature-2 (out of sync with develop)
      |
      o-feature-2-bugfix (in sync with feature-2)
```

The underlined branch is the one you are currently on.

In the next part, we'll see how to easily navigate between these branches.

[< Previous: Discovering branch layout](03-discovering-branch-layout.md) | [Next: Navigating between branches >](05-navigating-between-branches.md)
