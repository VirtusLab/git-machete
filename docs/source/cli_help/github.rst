.. _github:

github
------
**Usage:**

.. code-block:: shell

    git machete github <subcommand>

where ``<subcommand>`` is one of: ``anno-prs``, ``checkout-prs``, ``create-pr``, ``retarget-pr``.

Creates, checks out and manages GitHub PRs while keeping them reflected in branch definition file.

.. include:: github_api_access.rst

``anno-prs``:

  Annotates the branches based on their corresponding GitHub PR numbers and authors.
  Any existing annotations are overwritten for the branches that have an opened PR; annotations for the other branches remain untouched.
  Equivalent to ``git machete anno --sync-github-prs``.

``checkout-prs [--all | --by=<github-login> | --mine | <PR-number-1> ... <PR-number-N>]``:

  Check out the head branch of the given pull requests (specified by number),
  also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally.
  Once the specified pull requests are checked out locally, annotate local branches with corresponding pull request numbers.
  If only one PR is given, then switch the local repository's HEAD to its head branch.

  **Options:**

    ``--all``    Checkout all open PRs.

    ``--by``    Checkout open PRs authored by the given Github user.

      **Parameters:**
        ``<github-login>`` Github account name.

    ``--mine``    Checkout open PRs for the current user associated with the Github token.

  **Parameters:**
    ``<PR-number-1> ... <PR-number-N>``
      Pull request numbers to checkout.

``create-pr [--draft]``:

  Creates a PR for the current branch, using the upstream (parent) branch as the PR base.
  Once the PR is successfully created, annotates the current branch with the new PR's number.

  If ``.git/info/description`` file is present, its contents are used as PR description.
  If ``.git/info/milestone`` file is present, its contents (a single number --- milestone id) are used as milestone.
  If ``.git/info/reviewers`` file is present, its contents (one GitHub login per line) are used to set reviewers.

  **Options:**

    ``--draft``
      Creates the new PR as a draft.

``retarget-pr``:

  Sets the base of the current branch's PR to upstream (parent) branch, as seen by git machete (see ``git machete show up``).

``sync``:

  Synchronizes with the remote repository: removes untracked and unmanaged branches and also checks out open PRs for the current user associated with the Github token,
  also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally as well.

**Environment variables (all subcommands):**

``GITHUB_TOKEN``
    GitHub API token.
