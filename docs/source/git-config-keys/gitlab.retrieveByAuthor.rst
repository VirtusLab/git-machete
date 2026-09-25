When set to ``true``, commands that need to list open merge requests in the project
(such as ``gitlab anno-mrs``, ``gitlab checkout-mrs`` and ``traverse`` with GitLab integration)
download open MRs by author rather than every open MR in the project.

The author defaults to the current user as determined from the GitLab API token.
For ``gitlab checkout-mrs`` and ``gitlab update-mr-descriptions``, ``--mine`` explicitly selects the current user,
while ``--by=<username>`` selects a different author; chain reconstruction (walking upstream/downstream MRs)
uses that same author's MRs.
``gitlab anno-mrs`` does not support ``--mine`` or ``--by``; it always retrieves the current user's MRs when this key is enabled.
When checking out specific MR numbers, the author of the first given MR is used instead.

This can speed up operations considerably in projects with hundreds or thousands of open MRs,
at the cost of not being able to discover MRs opened by other users when traversing MR chains
(for example, when checking out an entire stack that includes MRs from multiple authors).

A valid GitLab API token is required when this key is set.

The ``--all`` flag to ``gitlab checkout-mrs`` and ``gitlab update-mr-descriptions``
still downloads all open MRs in the project, regardless of this setting.
