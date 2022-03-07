.. _clean:

clean
-----
**Usage:**

.. code-block:: shell

    git machete clean [-c|--checkout-my-github-prs] [-y|--yes]

Synchronizes with the remote repository:
    1. deletes unmanaged branches,
    2. if invoked with ``-c`` or ``--checkout-my-github-prs``, checks out open PRs for the current user associated with the Github token and also traverses the chain of pull requests upwards, adding branches one by one to git-machete and checks them out locally as well,
    3. deletes untracked managed branches that have no downstream branch.

No branch will be deleted unless explicitly confirmed by the user (or unless ``-y/--yes`` option is passed).
Equivalent of ``git machete github sync`` if invoked with ``-c`` or ``--checkout-my-github-prs``.

.. include:: github_api_access.rst

**Options:**

-c, --checkout-my-github-prs    Checkout your open PRs into local branches.
-y, --yes                  Don't ask for confirmation when deleting branches from git.

**Environment variables:**

``GITHUB_TOKEN``
    GitHub API token.
