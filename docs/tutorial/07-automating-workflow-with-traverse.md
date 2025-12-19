# Tutorial - Part 7: Automating workflow with traverse

If you have a chain of branches like `develop -> feature-1 -> feature-2`, and `develop` gets new commits, both `feature-1` and `feature-2` will become out of sync.

Updating them one by one with `git machete update` is fine, but `git-machete` can do better.

### The traverse command

The `traverse` command is a core feature of `git-machete`.
It walks through your branch tree and, for each branch, asks what you want to do if it's out of sync.

Run:
```shell
git machete traverse
```

For each branch that needs attention, it will ask you:
* **Rebase** onto parent?
* **Push** to remote?
* **Pull** from remote?
* **Slide out** (if it's already merged)?

### Powerful options

You can make `traverse` even more automated with flags:

* `--fetch` — run `git fetch` before starting.
* `--push` — automatically push branches that are in sync locally but ahead of remote.
* `--pull` — automatically pull branches that are behind remote.
* `--start-from=...` — start traversing from a specific branch.

### Example workflow

```shell
git machete traverse --fetch --push
```
This single command can:
1.  Fetch latest changes from the server.
2.  Rebase `feature-1` onto `develop`.
3.  Push `feature-1`.
4.  Rebase `feature-2` onto `feature-1`.
5.  Push `feature-2`.

...all while asking for your confirmation at each step (unless you use `-y` or `--yes` to skip confirmations).

Next, we'll look at a specialized command for merging children back into their parents.

[< Previous: Updating a branch](06-updating-a-branch.md) | [Next: Fast-forwarding with advance >](08-fast-forwarding-with-advance.md)
