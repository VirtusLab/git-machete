When set to ``true``, commands that need to list open pull requests in the repository
(such as ``github anno-prs``, ``github checkout-prs`` and ``traverse`` with GitHub integration)
will only download open PRs authored by the current user (as determined from the GitHub API token),
instead of all open PRs in the repository.

This can speed up operations considerably in repositories with hundreds or thousands of open PRs,
at the cost of not being able to discover PRs opened by other users when traversing PR chains
(for example, when checking out an entire stack that includes PRs from multiple authors).

A valid GitHub API token is required when this key is set.

The ``--all`` flag to ``github checkout-prs`` and ``github update-pr-descriptions``
still downloads all open PRs in the repository, regardless of this setting.

The ``--by=<login>`` flag to ``github checkout-prs`` and ``github update-pr-descriptions``
downloads open PRs authored by the given user directly (rather than filtering the current user's PRs),
so it keeps working for any author even when this key is set.
