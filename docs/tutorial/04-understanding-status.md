# Tutorial - Part 4: Understanding Status

The most frequently used command in `git-machete` is:
```shell
git machete status
```
It provides a "bird's eye view" of your repository.

### Color-coded Status

When you run `status`, you'll see your branch tree with colored edges (the lines connecting branches):

*   **Green**: The branch is **in sync** with its parent. All commits from the parent are already present in the child branch.
*   **Red**: The branch is **out of sync**. The parent has commits that are not yet in the child branch. It's time for a rebase!
*   **Gray**: The branch is **merged** into its parent. You can safely "slide it out" (more on that later).
*   **Yellow**: The branch is in sync with its parent, but its **remote tracking branch** has different commits (you might need to push or pull).

### Listing Commits

To see exactly what's on each branch, use:
```shell
git machete status --list-commits
```
(or `git machete s -l` for short).

This will list the commits that are **unique** to each branch. It's a great way to quickly remind yourself what you were working on in each feature branch.

### Example Output

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

[< Previous: Discovering Branch Layout](03-discovering-branch-layout.md) | [Next: Navigating Between Branches >](05-navigating-between-branches.md)
