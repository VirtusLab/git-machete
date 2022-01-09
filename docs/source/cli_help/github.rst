.. _github:

github
------
**Usage:**

.. code-block:: shell

    git machete github <subcommand>

where ``<subcommand>`` is one of: ``anno-prs``, ``checkout-prs``, ``create-pr``, ``retarget-pr``.

Creates, checks out and manages GitHub PRs while keeping them reflected in branch definition file.

To allow GitHub API access for private repositories (and also to perform side-effecting actions like opening a PR, even in case of public repositories),
a GitHub API token with ``repo`` scope is required, see https://github.com/settings/tokens. This will be resolved from the first of:

    1. ``GITHUB_TOKEN`` env var,
    2. content of the ``.github-token`` file in the home directory (``~``),
    3. current auth token from the ``gh`` GitHub CLI,
    4. current auth token from the ``hub`` GitHub CLI.

``anno-prs``:

  Annotates the branches based on their corresponding GitHub PR numbers and authors.
  Any existing annotations are overwritten for the branches that have an opened PR; annotations for the other branches remain untouched.
  Equivalent to ``git machete anno --sync-github-prs``.

``checkout-prs``:

  Check out the head branch of the given pull request (specified by number),
  also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally.
  Once pull request is checked out locally, annotate local branches with corresponding pull request numbers.

  **Parameters:**

    **<PR-number>**
      Pull request number to checkout.

``create-pr [--draft]``:

  Creates a PR for the current branch, using the upstream (parent) branch as the PR base.
  Once the PR is successfully created, annotates the current branch with the new PR's number.

  If ``.git/info/description`` file is present, its contents are used as PR description.
  If ``.git/info/milestone`` file is present, its contents (a single number --- milestone id) are used as milestone.
  If ``.git/info/reviewers`` file is present, its contents (one GitHub login per line) are used to set reviewers.

  **Options:**

    --draft
      Creates the new PR as a draft.

``retarget-pr``:

  Sets the base of the current branch's PR to upstream (parent) branch, as seen by git machete (see ``git machete show up``).

**Environment variables (all subcommands):**

``GITHUB_TOKEN``
    GitHub API token.
