# Tutorial - Part 5: Using branch annotations

Branch annotations allow you to attach short notes to your branches.
These notes are stored in the `.git/machete` file and displayed in the status output.

### Adding an annotation

To add a note to the current branch, run:
```shell
git machete anno "your note here"
```

If you run `git machete status`, you will see your note next to the branch name.

### Editing manually

Since annotations are just text in the layout file, you can also edit them by running `git machete edit`.
Anything that follows the branch name on the same line (separated by at least one space) is considered an annotation.

### Why use annotations?

* Primarily, to keep pull request numbers (see below).
* Keep track of the purpose — remind yourself what a branch is for.
* Status markers — mark branches as "DO NOT MERGE", "WIP", or "Ready for review".
* Collaboration — if you share your `.git/machete` file (though it's usually local), others can see your notes.

### Automatic annotations

To automatically annotate your branches with information from GitHub or GitLab, run:
```shell
git machete anno --sync-github-prs
```
(or `--sync-gitlab-mrs`) to fetch PR/MR numbers and authors for all branches that have them.

Note: in case of private repositories, this requires authorization —
see the [chapter on GitHub/GitLab integration](12-github-gitlab-integration.md).

[< Previous: Understanding `status`](04-understanding-status.md) | [Next: Navigating between branches >](06-navigating-between-branches.md)
