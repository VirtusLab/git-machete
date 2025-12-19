# Tutorial - Part 5: Navigating Between Branches

Instead of using `git checkout <branch-name>`, `git-machete` provides a much faster way to navigate your branch tree.

### Interactive Navigation

Run:
```shell
git machete go
```
This will open an interactive menu showing your branch layout.
You can use the arrow keys to select a branch and press **Enter** to check it out.

### Relative Navigation

If you prefer using the command line directly, you can navigate relative to your current branch in the layout:

*   `git machete go up`: Check out the parent branch.
*   `git machete go down`: Check out the first child branch.
*   `git machete go next`: Check out the next branch in the layout (depth-first).
*   `git machete go prev`: Check out the previous branch in the layout.

### Why use `go`?

*   **Less typing**: You don't have to type out long branch names.
*   **Context**: You navigate based on the *structure* of your work, not just branch names.
*   **Speed**: It's often much faster than `git checkout` + tab completion, especially with many similar-looking branch names.

Now that we can move around, let's learn how to keep our branches in sync.

[< Previous: Understanding Status](04-understanding-status.md) | [Next: Updating a Branch >](06-updating-a-branch.md)
