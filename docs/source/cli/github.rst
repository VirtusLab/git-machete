.. _github:

github
======
**Usage:**

.. code-block:: shell

    git machete github <subcommand>

where ``<subcommand>`` is one of: ``anno-prs``, ``checkout-prs``, ``create-pr``, ``retarget-pr``, ``restack-pr`` or ``update-pr-descriptions``.

Create, check out and manage GitHub PRs while keeping them reflected in branch layout file.

.. note::

    See **Git config keys** below in case the target repository cannot be detected automatically (for example, in case of GitHub Enterprise).

.. note::

    To allow GitHub API access for private repositories (and also to perform side-effecting actions like opening a PR,
    even in case of public repositories), a GitHub API token with ``repo`` scope is required, see https://github.com/settings/tokens.
    This will be resolved from the first of:

    #. ``GITHUB_TOKEN`` env var,
    #. content of the ``.github-token`` file in the home directory (``~``),
    #. current auth token from the ``gh`` GitHub CLI,
    #. current auth token from the ``hub`` GitHub CLI.

    GitHub Enterprise domains are supported.

    ``GITHUB_TOKEN`` is used indiscriminately for any domain, both github.com and Enterprise.

    ``gh`` and ``hub`` have their own built-in support for Enterprise domains, which is honored by git-machete.

    ``.github-token`` can have multiple per-domain entries in the format:

    .. code-block::

          ghp_mytoken_for_github_com
          ghp_myothertoken_for_git_example_org git.example.org
          ghp_yetanothertoken_for_git_example_com git.example.com

**Subcommands:**

``anno-prs [--with-urls]``:
    Annotate the branches based on their corresponding GitHub PR numbers and authors.
    Any existing annotations are overwritten for the branches that have an opened PR; annotations for the other branches remain untouched.
    Equivalent to ``git machete anno --sync-github-prs``.

    When the current user is NOT the author of the PR associated with that branch, adds ``rebase=no push=no`` branch qualifiers used by ``git machete traverse``,
    so that you don't rebase or push someone else's PR by accident (see help for :ref:`traverse`).

    **Options:**

    --with-urls                   Also include full PR URLs in the annotations (rather than just PR number).


``checkout-prs [--all | --by=<github-login> | --mine | <PR-number-1> ... <PR-number-N>]``:
    Check out the head branch of the given pull requests (specified by numbers or by a flag),
    also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally.
    Once the specified pull requests are checked out locally, annotate local branches with corresponding pull request numbers.
    If only one PR has been checked out, then switch the local repository's HEAD to its head branch.

    When the current user is NOT the author of the PR associated with that branch, adds ``rebase=no push=no`` branch qualifiers used by ``git machete traverse``,
    so that you don't rebase or push someone else's PR by accident (see help for :ref:`traverse`).

    **Options:**

    --all                   Checkout all open PRs.

    --by=<github-login>     Checkout open PRs authored by the given GitHub user, where ``<github-login>`` is the GitHub account name.

    --mine                  Checkout open PRs for the current user associated with the GitHub token.

    **Parameters:**

    ``<PR-number-1> ... <PR-number-N>``    Pull request numbers to checkout.

``create-pr [--draft] [--title=<title>] [-U|--update-related-descriptions] [-y|--yes]``:
    Create a PR for the current branch, using the upstream (parent) branch as the PR base.
    Once the PR is successfully created, annotate the current branch with the new PR's number.

    If ``.git/info/milestone`` file is present, its contents (a single number --- milestone id) are used as milestone.
    If ``.git/info/reviewers`` file is present, its contents (one GitHub login per line) are used to set reviewers.

    Unless ``--title`` is provided, the subject of the first unique commit of the branch is used as PR title.
    If ``.git/info/description`` or ``.github/pull_request_template.md`` template is present, its contents are used as PR description.
    Otherwise (or if ``machete.github.forceDescriptionFromCommitMessage`` is set), PR description is taken from message body of the first unique commit of the branch.

    If the newly-created PR is stacked atop another PR, the actual PR description posted to GitHub will include a generated section ("intro")
    listing the entire related chain of PRs. This section will be delimited with ``<!-- start git-machete generated -->``
    and ``<!-- end git-machete generated -->`` comments in Markdown. If a PR template file exists and contains these comments already,
    the generated section will be placed between them; otherwise, it will be placed at the beginning.

    **Options:**

    --draft                            Create the new PR as a draft.

    --title=<title>                    Set the PR title explicitly (the default is to use the first included commit's message as the title).

    -U, --update-related-descriptions  Update the generated sections ("intros") of PR descriptions that list the upstream and/or downstream PRs.
                                       See help for ``git machete github update-pr-descriptions --related`` for details.

    -y, --yes                          Do not ask for confirmation whether to push the branch.

``restack-pr [-U|--update-related-descriptions]``:
    Perform the following sequence of actions:

    #. If the PR for the current branch is ready for review, it gets converted into a draft.
    #. The PR is retargeted to its upstream (parent) branch, as in ``retarget-pr``.
    #. The branch is (force-)pushed into remote.
    #. If the PR has been converted to draft in step 1, it's reverted to ready for review state.

    The drafting/undrafting is useful in case the GitHub repository has set up `CODEOWNERS <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners>`_.
    Draft PRs don't get code owners automatically added as reviewers.

    **Options:**

    -U, --update-related-descriptions  Update the generated sections ("intros") of PR descriptions that list the upstream and/or downstream PRs.
                                       See help for ``git machete github update-pr-descriptions --related`` for details.

``retarget-pr [-b|--branch=<branch>] [--ignore-if-missing] [-U|--update-related-descriptions]``:
    Set the base of the current (or specified) branch's PR to upstream (parent) branch, as seen by git machete (see ``git machete show up``).

    If after changing the base the PR ends up stacked atop another PR, the PR description posted to GitHub will include
    a generated section ("intro") listing the entire related chain of PRs.

    This intro will be updated or removed accordingly with the subsequent runs of ``retarget-pr``, even if the base branch is already up to date.

    **Options:**

    -b, --branch=<branch>              Specify the branch for which the associated PR base will be set to its upstream (parent) branch. The current branch is used if the option is absent.

    --ignore-if-missing                Ignore errors and quietly terminate execution if there is no PR opened for current (or specified) branch.

    -U, --update-related-descriptions  Update the generated sections ("intros") of PR descriptions that list the upstream and/or downstream PRs.
                                       See help for ``git machete github update-pr-descriptions --related`` for details.

``sync``:
    **Deprecated.** Use ``github checkout-prs --mine``, ``delete-unmanaged`` and ``slide-out --removed-from-remote``.

    Synchronize with the remote repository:

    #. check out open PRs for the current user associated with the GitHub token and also traverses the chain of pull requests upwards,
       adding branches one by one to git-machete and checks them out locally as well,
    #. delete unmanaged branches,
    #. delete untracked managed branches that have no downstream branch.

``update-pr-descriptions [--all | --by=<github-login> | --mine | --related]``:
    Update the generated sections ("intros") of PR descriptions that list the upstream and/or downstream PRs
    (depending on ``machete.github.prDescriptionIntroStyle`` git config key).

    **Options:**

    --all                Update PR descriptions for all PRs in the repository.

    --by=<github-login>  Update PR descriptions for all PRs authored by the given GitHub user, where ``<github-login>`` is the GitHub account name.

    --mine               Update PR descriptions for all PRs opened by the current user associated with the GitHub token.

    --related            Update PR descriptions for all PRs that are upstream and/or downstream of the PR for the current branch.
                         If ``machete.github.prDescriptionIntroStyle`` is ``up-only`` (default) or ``up-only-no-branches``, then only downstream PR descriptions are updated.
                         If ``machete.github.prDescriptionIntroStyle`` is ``full`` or ``full-no-branches``, then both downstream and upstream PR descriptions are updated.

**Git config keys:**

``machete.github.{domain,remote,organization,repository}`` (all subcommands):
  .. include:: git-config-keys/github_access.rst

``machete.github.annotateWithUrls`` (all subcommands):
  .. include:: git-config-keys/github_annotateWithUrls.rst

``machete.github.forceDescriptionFromCommitMessage`` (``create-pr`` only):
  .. include:: git-config-keys/github_forceDescriptionFromCommitMessage.rst

``machete.github.prDescriptionIntroStyle`` (``create-pr``, ``restack-pr`` and ``retarget-pr``):
  .. include:: git-config-keys/github_prDescriptionIntroStyle.rst

**Environment variables (all subcommands):**

``GITHUB_TOKEN``
    GitHub API token.
