# Tutorial - Part 6: Navigating between branches

As an alternative to `git checkout <branch-name>`, `git-machete` provides a faster way to navigate your branch tree.

### Interactive navigation

To open an interactive menu showing your branch layout, run:
```shell
git machete go
```
You can use the arrow keys to select a branch and press Enter to check it out.

### Relative navigation

If you prefer using the command line directly, you can navigate relative to your current branch in the layout:

* `git machete go up`: Check out the parent branch.
* `git machete go down`: Check out a child branch.
* `git machete go next`: Check out the next branch in the layout (depth-first).
* `git machete go prev`: Check out the previous branch in the layout.

### A note on compatibility

`git-machete` doesn't replace or interfere with standard git commands.
You can still use `git checkout`, `git rebase`, `git merge`, and all other git commands as usual.
`git-machete` is simply a wrapper that provides convenient shortcuts over the existing git concepts like branches, commits, and rebases.
It doesn't fundamentally change how git operates — it just makes common workflows faster and less error-prone.

[< Previous: Using branch annotations](05-using-branch-annotations.md) | [Next: Updating a branch with a rebase >](07-updating-a-branch-with-a-rebase.md)
