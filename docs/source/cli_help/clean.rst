.. _clean:

clean
-----
**Usage:**

.. code-block:: shell

    git machete clean [-c|--checkout-my-github-prs] [-y|--yes]

If invoked without any flag, deletes untracked managed branches with no downstream branch and unmanaged branches.
No branch will be deleted unless explicitly confirmed by the user (or unless ``-y/--yes`` option is passed).

If invoked with ``-c`` or ``--checkout-my-github-prs``, also checks out your open PRs into local branches.
Equivalent of ``git machete github sync``.

.. include:: github_api_access.rst

**Options:**

-c, --checkout-my-github-prs    Checkout your open PRs into local branches.
-y, --yes                  Don't ask for confirmation when deleting branches from git.

**Environment variables:**

``GITHUB_TOKEN``
    GitHub API token.
