.. _gitlab:

gitlab
======
**Usage:**

.. code-block:: shell

    git machete gitlab <subcommand>

where ``<subcommand>`` is one of: ``anno-mrs``, ``checkout-mrs``, ``create-mr``, ``retarget-mr``.

Creates, checks out and manages GitLab MRs while keeping them reflected in branch layout file.

.. include:: gitlab_api_access.rst

.. note::
  See **Git config keys** below in case the target repository cannot be detected automatically (for example, in case of GitLab Enterprise).

**Subcommands:**

``anno-mrs [--with-urls]``:
    Annotates the branches based on their corresponding GitLab MR numbers and authors.
    Any existing annotations are overwritten for the branches that have an opened MR; annotations for the other branches remain untouched.
    Equivalent to ``git machete anno --sync-gitlab-mrs``.

    When the current user is NOT the author of the MR associated with that branch, adds ``rebase=no push=no`` branch qualifiers used by ``git machete traverse``,
    so that you don't rebase or push someone else's MR by accident (see help for :ref:`traverse`).

    **Options:**

    --with-urls                   Also include full MR URLs in the annotations (rather than just MR number).


``checkout-mrs [--all | --by=<gitlab-login> | --mine | <MR-number-1> ... <MR-number-N>]``:
    Check out the head branch of the given pull requests (specified by numbers or by a flag),
    also traverse chain of pull requests upwards, adding branches one by one to git-machete and check them out locally.
    Once the specified pull requests are checked out locally, annotate local branches with corresponding pull request numbers.
    If only one MR has been checked out, then switch the local repository's HEAD to its head branch.

    When the current user is NOT the author of the MR associated with that branch, adds ``rebase=no push=no`` branch qualifiers used by ``git machete traverse``,
    so that you don't rebase or push someone else's MR by accident (see help for :ref:`traverse`).

    **Options:**

    --all                   Checkout all open MRs.

    --by=<gitlab-login>     Checkout open MRs authored by the given GitLab user, where ``<gitlab-login>`` is the GitLab account name.

    --mine                  Checkout open MRs for the current user associated with the GitLab token.

    **Parameters:**

    ``<MR-number-1> ... <MR-number-N>``    Pull request numbers to checkout.

``create-mr [--draft] [--title=<title>] [--yes]``:
    Creates a MR for the current branch, using the upstream (parent) branch as the MR base.
    Once the MR is successfully created, annotates the current branch with the new MR's number.

    If ``.git/info/milestone`` file is present, its contents (a single number --- milestone id) are used as milestone.
    If ``.git/info/reviewers`` file is present, its contents (one GitLab login per line) are used to set reviewers.

    The subject of the first unique commit of the branch is used as MR title.
    If ``.git/info/description`` or ``.gitlab/merge_request_templates/Default.md`` file is present, its contents are used as MR description.
    Otherwise (or if ``machete.gitlab.forceDescriptionFromCommitMessage`` is set), MR description is taken from message body of the first unique commit of the branch.

    If the newly-created MR is stacked atop another MR, the actual MR description posted to GitLab will be prepended with a section
    listing the entire related chain of MRs.

    **Options:**

    --draft            Create the new MR as a draft.

    --title=<title>    Set the MR title explicitly (the default is to use the first included commit's message as the title).

    --yes              Do not ask for confirmation whether to push the branch.

``restack-mr``:
    Perform the following sequence of actions:
    1. If the MR for the current branch is ready for review, it gets converted to a draft.
    2. The branch is (force-)pushed into remote.
    3. The MR is retargeted to its upstream (parent) branch, as in ``retarget-mr``.
    4. If the MR has been converted to draft in step 1, it's reverted to ready for review state.

    The drafting/undrafting is useful in case the GitLab repository has set up ????????.
    Draft MRs don't get code owners automatically added as reviewers.

``retarget-mr [-b|--branch=<branch>] [--ignore-if-missing]``:
    Sets the base of the current (or specified) branch's MR to upstream (parent) branch, as seen by git machete (see ``git machete show up``).

    If after changing the base the MR ends up stacked atop another MR, the MR description posted to GitLab will be prepended with a section
    listing the entire related chain of MRs.

    This header will be updated or removed accordingly with the subsequent runs of ``retarget-mr``.

    **Options:**

    -b, --branch=<branch>     Specify the branch for which the associated MR base will be set to its upstream (parent) branch. The current branch is used if the option is absent.

    --ignore-if-missing       Ignore errors and quietly terminate execution if there is no MR opened for current (or specified) branch.

**Git config keys:**

FILL UP!!!!!!!!

**Environment variables (all subcommands):**

``GITLAB_TOKEN``
    GitLab API token.
