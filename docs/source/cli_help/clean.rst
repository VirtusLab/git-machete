.. _clean:

clean
----
**Usage:**

.. code-block:: shell

    git machete clean [-c|--checkout-my-github-prs]

If invoked without any flag, deletes untracked and unmanaged branches.

If invoked with ``-c`` or ``--checkout-my-github-prs``, also checks out your open PRs into local branches.

.. include:: github_api_access.rst

**Options:**

``-c, --checkout-my-github-prs``    Checkout your open PRs into local branches.

**Environment variables:**

``GITHUB_TOKEN``
    GitHub API token.
