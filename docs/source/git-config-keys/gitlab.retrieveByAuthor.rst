When set to ``true``, commands that need to list open merge requests in the project
(such as ``gitlab anno-mrs``, ``gitlab checkout-mrs`` and ``traverse`` with GitLab integration)
download open MRs by author rather than every open MR in the project.

By default (and with ``--mine``), that author is the current user as determined from the GitLab API token.
The ``--by=<username>`` flag selects a different author instead; chain reconstruction (walking upstream/downstream MRs)
uses that same author's MRs, not the current user's.

This can speed up operations considerably in projects with hundreds or thousands of open MRs,
at the cost of not being able to discover MRs opened by other users when traversing MR chains
(for example, when checking out an entire stack that includes MRs from multiple authors).

A valid GitLab API token is required when this key is set.

The ``--all`` flag to ``gitlab checkout-mrs`` and ``gitlab update-mr-descriptions``
still downloads all open MRs in the project, regardless of this setting.
