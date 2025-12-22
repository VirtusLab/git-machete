# Tutorial - Part 10: Fast-forwarding with `advance`

Once you've finished work on a child branch and want to merge it into its parent,
you might want to do a fast-forward merge to keep the history linear.

### The `advance` command

When you are on a parent branch (e.g., `develop`),
and you want to fast-forward it to its child branch (e.g., `feature-1`), run:

```shell
git machete advance
```

### How it works

1.  It checks if there is exactly one child branch of the current branch.
2.  If there are multiple children, it asks you to choose one.
3.  It fast-forwards the current branch to the selected child.
4.  It optionally pushes the parent branch to the remote.
5.  It "slides out" the child branch from the layout (since its commits are now part of the parent).

### Example

Before `advance`:
```text
  develop
    feature-1* (current branch)
```

Run `git machete go up` to get to `develop`.
Run `git machete advance`.

After `advance`:
```text
  develop* (current branch; now at the same commit as feature-1 was)
```

The `feature-1` branch is now merged into `develop` and removed from the machete layout.

[< Previous: Automating workflow with `traverse`](09-automating-workflow-with-traverse.md) | [Next: Cleaning up with `slide-out` >](11-cleaning-up-with-slide-out.md)
