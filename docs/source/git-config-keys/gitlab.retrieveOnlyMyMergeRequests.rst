When set to ``true``, commands that need to list open merge requests in the project
(such as ``gitlab anno-mrs``, ``gitlab checkout-mrs`` and ``traverse`` with GitLab integration)
will only download open MRs authored by the current user (as determined from the GitLab API token),
instead of all open MRs in the project.

This can speed up operations considerably in projects with hundreds or thousands of open MRs,
at the cost of not being able to discover MRs opened by other users when traversing MR chains
(for example, when checking out an entire stack that includes MRs from multiple authors).

A valid GitLab API token is required when this key is set.

The ``--all`` flag to ``gitlab checkout-mrs`` and ``gitlab update-mr-descriptions``
still downloads all open MRs in the project, regardless of this setting.

The ``--by=<username>`` flag to ``gitlab checkout-mrs`` and ``gitlab update-mr-descriptions``
downloads open MRs authored by the given user directly (rather than filtering the current user's MRs),
so it keeps working for any author even when this key is set.
