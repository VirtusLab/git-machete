.. _github:

github
======
**Usage:**

.. code-block:: shell

    git machete github <subcommand>

where ``<subcommand>`` is one of: ``anno-prs``, ``checkout-prs``, ``create-pr``, ``retarget-pr``.

Creates, checks out and manages GitHub PRs while keeping them reflected in branch layout file.

.. include:: github_api_access.rst

.. note::
  See **Git config keys** below in case the target repository cannot be detected automatically (for example, in case of GitHub Enterprise).

**Subcommands:**

``anno-prs [--with-urls]``:
    Annotates the branches based on their corresponding GitHub PR numbers and authors.
    Any existing annotations are overwritten for the branches that have an opened PR; annotations for the other branches remain untouched.
    Equivalent to ``git machete anno --sync-github-prs``.

    When the current user is NOT the owner of the PR associated with that branch, adds ``rebase=no push=no`` branch qualifiers used by ``git machete traverse``,
    so that you don't rebase or push someone else's PR by accident (see help for :ref:`traverse`).

    **Options:**

    --with-urls                   Also include full PR URLs in the annotations (rather than just PR number).


``checkout-prs [--all | --by=<github-login> | --mine | <PR-number-1> ... <PR-number-N>]``:
    Check out the head branch of the given pull requests (specified by numbers or by a flag),
    also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally.
    Once the specified pull requests are checked out locally, annotate local branches with corresponding pull request numbers.
    If only one PR has been checked out, then switch the local repository's HEAD to its head branch.

    When the current user is NOT the owner of the PR associated with that branch, adds ``rebase=no push=no`` branch qualifiers used by ``git machete traverse``,
    so that you don't rebase or push someone else's PR by accident (see help for :ref:`traverse`).

    **Options:**

    --all                   Checkout all open PRs.

    --by=<github-login>     Checkout open PRs authored by the given GitHub user, where ``<github-login>`` is the GitHub account name.

    --mine                  Checkout open PRs for the current user associated with the GitHub token.

    **Parameters:**

    ``<PR-number-1> ... <PR-number-N>``    Pull request numbers to checkout.

``create-pr [--draft] [--title=<title>] [--yes]``:
    Creates a PR for the current branch, using the upstream (parent) branch as the PR base.
    Once the PR is successfully created, annotates the current branch with the new PR's number.

    If ``.git/info/milestone`` file is present, its contents (a single number --- milestone id) are used as milestone.
    If ``.git/info/reviewers`` file is present, its contents (one GitHub login per line) are used to set reviewers.

    The subject of the first unique commit of the branch is used as PR title.
    If ``.git/info/description`` or ``.github/pull_request_template.md`` file is present, its contents are used as PR description.
    Otherwise (or if ``machete.github.forceDescriptionFromCommitMessage`` is set), PR description is taken from message body of the first unique commit of the branch.

    If the newly-created PR is stacked atop another PR, the actual PR description posted to GitHub will be prepended with the following header:

    ``# Based on PR #<number of PR for base branch>``

    **Options:**

    --draft            Create the new PR as a draft.

    --title=<title>    Set the PR title explicitly (the default is to use the first included commit's message as the title).

    --yes              Do not ask for confirmation whether to push the branch.

``restack-pr``:
    Perform the following sequence of actions:
    1. If the PR for the current branch is ready for review, it gets converted to a draft.
    2. The branch is (force-)pushed into remote.
    3. The PR is retargeted to its upstream (parent) branch, as in ``retarget-pr``.
    4. If the PR has been converted to draft in step 1, it's reverted to ready for review state.

    The drafting/undrafting is useful in case the GitHub repository has set up `CODEOWNERS <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners>`_.
    Draft PRs don't get code owners automatically added as reviewers.

``retarget-pr [-b|--branch=<branch>] [--ignore-if-missing]``:
    Sets the base of the current (or specified) branch's PR to upstream (parent) branch, as seen by git machete (see ``git machete show up``).

    If after changing the base, the PR ends up stacked atop another PR, the PR description at GitHub will be prepended with the following header:

    ``# Based on PR #<number of PR for base branch>``

    This header will be updated or removed accordingly with the subsequent runs of ``retarget-pr``.

    **Options:**

    -b, --branch=<branch>     Specify the branch for which the associated PR base will be set to its upstream (parent) branch. The current branch is used if the option is absent.

    --ignore-if-missing       Ignore errors and quietly terminate execution if there is no PR opened for current (or specified) branch.

``sync``:
    **Deprecated.** Use ``github checkout-prs --mine``, ``delete-unmanaged`` and ``slide-out --removed-from-remote``.

    Synchronizes with the remote repository:

      1. checks out open PRs for the current user associated with the GitHub token and also traverses the chain of pull requests upwards,
         adding branches one by one to git-machete and checks them out locally as well,
      2. deletes unmanaged branches,
      3. deletes untracked managed branches that have no downstream branch.

**Git config keys:**

``machete.github.annotateWithUrls`` (all subcommands):
  .. include:: github_annotateWithUrls_config_key.rst

``machete.github.forceDescriptionFromCommitMessage`` (``create-pr`` only):
  .. include:: github_forceDescriptionFromCommitMessage_config_key.rst

``machete.github.{domain,remote,organization,repository}`` (all subcommands):
  .. include:: github_access_config_keys.rst
      :start-line: 2

**Environment variables (all subcommands):**

``GITHUB_TOKEN``
    GitHub API token.
