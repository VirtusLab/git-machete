.. _clean:

clean
=====
**Usage:**

.. code-block:: shell

    git machete clean [-c|--checkout-my-github-prs] [-y|--yes]

**Deprecated.** Use ``github checkout-prs --mine``, ``delete-unmanaged`` and ``slide-out --removed-from-remote``.

Synchronizes with the remote repository:

#. if invoked with ``-H`` or ``--checkout-my-github-prs``, checks out open PRs for the current user associated with the GitHub token
   and also traverses the chain of pull requests upwards, adding branches one by one to git-machete and checks them out locally as well,
#. deletes unmanaged branches,
#. deletes untracked managed branches that have no downstream branch.

No branch will be deleted unless explicitly confirmed by the user (or unless ``-y/--yes`` option is passed).
Equivalent of ``git machete github sync`` if invoked with ``-H`` or ``--checkout-my-github-prs``.

.. note::

  See the help for :ref:`github` for how to configure GitHub API access.
  TL;DR: ``GITHUB_TOKEN`` env var or ``~/.github-token`` file or ``gh``/``hub`` CLI configs if exist.
  For enterprise domains, non-standard URLs etc., check git config keys in ``github`` help.

**Options:**

-c, --checkout-my-github-prs    Checkout your open PRs into local branches.

-y, --yes                       Don't ask for confirmation when deleting branches from git.

**Environment variables:**

``GITHUB_TOKEN``
    GitHub API token.
