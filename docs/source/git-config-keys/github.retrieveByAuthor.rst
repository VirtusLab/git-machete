When set to ``true``, commands that need to list open pull requests in the repository
(such as ``github anno-prs``, ``github checkout-prs`` and ``traverse`` with GitHub integration)
download open PRs by author rather than every open PR in the repository.

By default (and with ``--mine``), that author is the current user as determined from the GitHub API token.
The ``--by=<login>`` flag selects a different author instead; chain reconstruction (walking upstream/downstream PRs)
uses that same author's PRs, not the current user's.
When checking out specific PR numbers, the author of the first given PR is used instead.

This can speed up operations considerably in repositories with hundreds or thousands of open PRs,
at the cost of not being able to discover PRs opened by other users when traversing PR chains
(for example, when checking out an entire stack that includes PRs from multiple authors).

A valid GitHub API token is required when this key is set.

The ``--all`` flag to ``github checkout-prs`` and ``github update-pr-descriptions``
still downloads all open PRs in the repository, regardless of this setting.
