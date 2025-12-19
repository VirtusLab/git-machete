# Tutorial - Part 9: Automating workflow with traverse

If you have a chain of branches like `feature-2 -> feature-1 -> develop`, and `develop` gets new commits, both `feature-1` and `feature-2` will become out of sync.

Updating them one by one with `git machete update` is fine, but `git-machete` can do better.

### The traverse command

The `traverse` command is a core feature of `git-machete`.
To walk through your branch tree and sync your branches, run:
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

[< Previous: Squashing and reapplying](08-squashing-and-reapplying.md) | [Next: Fast-forwarding with advance >](10-fast-forwarding-with-advance.md)
