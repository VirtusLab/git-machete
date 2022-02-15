.. _clean:

clean
----
**Usage:**

.. code-block:: shell

    git machete clean [-c|--checkout-my-github-prs]

If invoked without any flag, deletes untracked and unmanaged branches.

If invoked with ``-c`` or ``--checkout-my-github-prs``, checkouts your open PRs into local branches.

To allow GitHub API access for private repositories (and also to perform side-effecting actions like opening a PR, even in case of public repositories),
a GitHub API token with ``repo`` scope is required, see https://github.com/settings/tokens. This will be resolved from the first of:

    1. ``GITHUB_TOKEN`` env var,
    2. current auth token from the ``gh`` GitHub CLI,
    3. current auth token from the ``hub`` GitHub CLI.

**Options:**

``-c, --checkout-my-github-prs``    Checkout your open PRs into local branches.

**Environment variables:**

``GITHUB_TOKEN``
    GitHub API token.
