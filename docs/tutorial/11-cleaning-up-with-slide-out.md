# Tutorial - Part 11: Cleaning up with `slide-out`

When a feature branch is merged into its parent, it usually appears in `git machete status` with a **gray edge**.
This means the branch is no longer needed in the layout.

### The `slide-out` command

To remove a merged branch from the layout and connect its children directly to its parent, use:

```shell
git machete slide-out
```

### What it does

1.  Removes the current branch from the `.git/machete` file.
2.  If the branch had any children, they are now attached to the parent of the removed branch.
3.  Optionally deletes the branch locally and/or on the remote.

### Example

Before `slide-out`:
```text
  develop
    feature-1 (merged)
      feature-1-bugfix
```

After `git machete slide-out` on `feature-1`:
```text
  develop
    feature-1-bugfix
```

### Why use slide-out?

* Keep layout clean — remove branches that are done.
* Automatic re-parenting — you don't have to manually update `.git/machete` to connect `feature-1-bugfix` to `develop`.
* Safety — `git-machete` will warn you if you're trying to slide out a branch that hasn't been merged yet (unless you use `--anyway`).

[< Previous: Fast-forwarding with `advance`](10-fast-forwarding-with-advance.md) | [Next: GitHub/GitLab integration >](12-github-gitlab-integration.md)
