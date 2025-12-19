# Tutorial - Part 12: GitHub/GitLab integration

`git-machete` is particularly useful when working with Pull Requests (PRs) or Merge Requests (MRs).

### Checking out PRs/MRs

If you want to review someone else's work, you can check out their PRs and automatically add them to your machete layout:

```shell
git machete github checkout-prs --mine
```
This will:
1.  Find all PRs opened by you.
2.  Check them out locally.
3.  Add them to your `.git/machete` file in the correct order (if they are stacked).

You can also checkout specific PRs by number: `git machete github checkout-prs 123 125`.

### Creating PRs/MRs

Creating a PR from your current branch is easy:

```shell
git machete github create-pr
```
`git-machete` will:
1.  Identify the parent branch from your layout.
2.  Use it as the "base" for the PR.
3.  Open a browser window to create the PR (or create it directly via API if a token is provided).

### PR chains

`git-machete` can include a "PR chain" in the PR description, showing all the dependent PRs.
This helps reviewers understand the context of your changes.

### Configuration

To use these features, you might need to set up a GitHub/GitLab token.
See the [full documentation](https://git-machete.readthedocs.io/en/stable/cli/github.html) for details.

[< Previous: Cleaning up with `slide-out`](11-cleaning-up-with-slide-out.md) | [Next: Conclusion and next steps >](13-conclusion.md)
