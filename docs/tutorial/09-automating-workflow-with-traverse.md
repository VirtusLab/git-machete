# Tutorial - Part 9: Automating workflow with `traverse`

If you have a chain of branches like `feature-2` → `feature-1` → `develop`,
and `develop` gets new commits, both `feature-1` and `feature-2` will become out of sync.

Updating them one by one with `git machete update` is fine, but `git-machete` can do better.

### The `traverse` command

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
* `--whole` — walk through the entire branch tree instead of starting from the current branch.
* `-W` — equivalent to `--fetch --whole`.
* `--yes` or `-y` — automatically confirm all actions.

### Example workflow

```shell
git machete traverse -W -y
```
This single command will:
1.  Fetch latest changes from the server.
2.  Walk through all branches in your layout.
3.  Rebase any out-of-sync branches.
4.  Push or pull branches as needed.
5.  Slide out merged branches.

...all without asking for a confirmation.

[< Previous: Squashing and reapplying](08-squashing-and-reapplying.md) | [Next: Fast-forwarding with `advance` >](10-fast-forwarding-with-advance.md)
