# Tutorial - Part 5: Navigating between branches

Instead of using `git checkout <branch-name>`, `git-machete` provides a much faster way to navigate your branch tree.

### Interactive navigation

Run:
```shell
git machete go
```
This will open an interactive menu showing your branch layout.
You can use the arrow keys to select a branch and press **Enter** to check it out.

### Relative navigation

If you prefer using the command line directly, you can navigate relative to your current branch in the layout:

* `git machete go up`: Check out the parent branch.
* `git machete go down`: Check out the first child branch.
* `git machete go next`: Check out the next branch in the layout (depth-first).
* `git machete go prev`: Check out the previous branch in the layout.

### Why use go?

* Less typing — you don't have to type out long branch names.
* Context — you navigate based on the structure of your work, not just branch names.
* Speed — it's often much faster than `git checkout` + tab completion, especially with many similar-looking branch names.

Now that we can move around, let's learn how to keep our branches in sync.

[< Previous: Understanding status](04-understanding-status.md) | [Next: Updating a branch >](06-updating-a-branch.md)
