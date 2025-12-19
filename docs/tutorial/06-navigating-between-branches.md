# Tutorial - Part 6: Navigating between branches

Instead of using `git checkout <branch-name>`, `git-machete` provides a much faster way to navigate your branch tree.

### Interactive navigation

To open an interactive menu showing your branch layout, run:
```shell
git machete go
```
You can use the arrow keys to select a branch and press **Enter** to check it out.

### Relative navigation

If you prefer using the command line directly, you can navigate relative to your current branch in the layout:

* `git machete go up`: Check out the parent branch.
* `git machete go down`: Check out a child branch.
* `git machete go next`: Check out the next branch in the layout (depth-first).
* `git machete go prev`: Check out the previous branch in the layout.

### Why use `go`?

* Less typing — you don't have to type out long branch names.
* Context — you navigate based on the structure of your work, not just branch names.
* Speed — it's often much faster than `git checkout` + tab completion, especially with many similar-looking branch names.

[< Previous: Using branch annotations](05-using-branch-annotations.md) | [Next: Updating a branch with a rebase >](07-updating-a-branch-with-a-rebase.md)
