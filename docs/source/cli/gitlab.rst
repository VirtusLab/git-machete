.. _gitlab:

gitlab
======
**Usage:**

.. code-block:: shell

    git machete gitlab <subcommand>

where ``<subcommand>`` is one of: ``anno-mrs``, ``checkout-mrs``, ``create-mr``, ``retarget-mr``, ``restack-mr`` or ``update-mr-descriptions``.

Create, check out and manage GitLab MRs while keeping them reflected in branch layout file.

.. note::

    See **Git config keys** below in case the target project cannot be detected automatically (for example, in case of GitLab self-managed instance).

.. note::

    To allow GitLab API access for private projects (and also to perform side-effecting actions like opening an MR,
    even in case of public projects), a GitLab API token with ``api`` scope is required, see https://gitlab.com/-/user_settings/personal_access_tokens.
    This will be resolved from the first of:

    #. ``GITLAB_TOKEN`` env var,
    #. content of the ``.gitlab-token`` file in the home directory (``~``),
    #. current auth token from the ``glab`` GitLab CLI.

    Self-managed GitLab domains are supported.

    ``GITLAB_TOKEN`` is used indiscriminately for any domain, both for gitlab.com and a self-managed instance.

    ``glab`` has its own built-in support for non-gitlab.com domains, which is honored by git-machete.

    ``.gitlab-token`` can have multiple per-domain entries in the format:

    .. code-block::

          glpat-mytoken_for_gitlab_com
          glpat-myothertoken_for_git_example_org git.example.org
          glpat-yetanothertoken_for_git_example_com git.example.com

**Subcommands:**

``anno-mrs [--with-urls]``:
    Annotate the branches based on their corresponding GitLab MR numbers and authors.
    Any existing annotations are overwritten for the branches that have an opened MR; annotations for the other branches remain untouched.
    Equivalent to ``git machete anno --sync-gitlab-mrs``.

    When the current user is NOT the author of the MR associated with that branch, adds ``rebase=no push=no`` branch qualifiers used by ``git machete traverse``,
    so that you don't rebase or push someone else's MR by accident (see help for :ref:`traverse`).

    **Options:**

    --with-urls                   Also include full MR URLs in the annotations (rather than just MR number).


``checkout-mrs [--all | --by=<gitlab-login> | --mine | <MR-number-1> ... <MR-number-N>]``:
    Check out the source branch of the given merge requests (specified by numbers or by a flag),
    also traverse chain of merge requests upwards, adding branches one by one to git-machete and check them out locally.
    Once the specified merge requests are checked out locally, annotate local branches with corresponding merge request numbers.
    If only one MR has been checked out, then switch the local repository's HEAD to its source branch.

    When the current user is NOT the author of the MR associated with that branch, adds ``rebase=no push=no`` branch qualifiers used by ``git machete traverse``,
    so that you don't rebase or push someone else's MR by accident (see help for :ref:`traverse`).

    **Options:**

    --all                   Checkout all open MRs.

    --by=<gitlab-login>     Checkout open MRs authored by the given GitLab user, where ``<gitlab-login>`` is the GitLab account name.

    --mine                  Checkout open MRs for the current user associated with the GitLab token.

    **Parameters:**

    ``<MR-number-1> ... <MR-number-N>``    Merge request numbers to checkout.

``create-mr [--draft] [--title=<title>] [-U|--update-related-descriptions] [-y|--yes]``:
    Create an MR for the current branch, using the upstream (parent) branch as the MR source branch.
    Once the MR is successfully created, annotate the current branch with the new MR's number.

    If ``.git/info/milestone`` file is present, its contents (a single number --- milestone id) are used as milestone.
    Note that you need to use a global (not per-project) milestone id. Look for something like ``Milestone ID: 4489529`` on milestone web page.

    If ``.git/info/reviewers`` file is present, its contents (one GitLab login per line) are used to set reviewers.

    Unless ``--title`` is provided, the subject of the first unique commit of the branch is used as MR title.
    If ``.git/info/description`` or ``.gitlab/merge_request_templates/Default.md`` template is present, its contents are used as MR description.
    Otherwise (or if ``machete.gitlab.forceDescriptionFromCommitMessage`` is set), MR description is taken from message body of the first unique commit of the branch.

    If the newly-created MR is stacked atop another MR, the actual MR description posted to GitLab will include a generated section ("intro")
    listing the entire related chain of MRs. This section will be delimited with ``<!-- start git-machete generated -->``
    and ``<!-- end git-machete generated -->`` comments in Markdown. If an MR template file exists and contains these comments already,
    the generated section will be placed between them; otherwise, it will be placed at the beginning.

    **Options:**

    --draft                            Create the new MR as a draft.

    --title=<title>                    Set the MR title explicitly (the default is to use the first included commit's message as the title).

    -U, --update-related-descriptions  Update the generated sections ("intros") of MR descriptions that list the upstream and/or downstream MRs.
                                       See help for ``git machete gitlab update-mr-descriptions --related`` for details.

    -y, --yes                          Do not ask for confirmation whether to push the branch.

``restack-mr [-U|--update-related-descriptions]``:
    Perform the following sequence of actions:

    #. If the MR for the current branch is ready for review, it gets converted into a draft.
    #. The MR is retargeted to its upstream (parent) branch, as in ``retarget-mr``.
    #. The branch is (force-)pushed into remote.
    #. If the MR has been converted to draft in step 1, it's reverted to ready for review state.

    The drafting/undrafting is useful in case the GitLab project has set up `code owners <https://docs.gitlab.com/ee/user/project/codeowners/>`_.
    Draft MRs don't get code owners automatically added as reviewers.

    **Options:**

    -U, --update-related-descriptions  Update the generated sections ("intros") of MR descriptions that list the upstream and/or downstream MRs.
                                       See help for ``git machete gitlab update-mr-descriptions --related`` for details.

``retarget-mr [-b|--branch=<branch>] [--ignore-if-missing] [-U|--update-related-descriptions]``:
    Set the target of the current (or specified) branch's MR to upstream (parent) branch, as seen by git machete (see ``git machete show up``).

    If after changing the base the MR ends up stacked atop another MR, the MR description posted to GitLab will include
    a generated section ("intro") listing the entire related chain of MRs.

    This intro will be updated or removed accordingly with the subsequent runs of ``retarget-mr``, even if the target branch is already up to date.

    **Options:**

    -b, --branch=<branch>              Specify the branch for which the associated MR source branch will be set to its upstream (parent) branch. The current branch is used if the option is absent.

    --ignore-if-missing                Ignore errors and quietly terminate execution if there is no MR opened for current (or specified) branch.

    -U, --update-related-descriptions  Update the generated sections ("intros") of MR descriptions that list the upstream and/or downstream MRs.
                                       See help for ``git machete gitlab update-mr-descriptions --related`` for details.

``update-mr-descriptions [--all | --by=<gitlab-login> | --mine | --related]``:
    Update the generated sections ("intros") of MR descriptions that list the upstream and/or downstream MRs
    (depending on ``machete.gitlab.mrDescriptionIntroStyle`` git config key).

    **Options:**

    --all                Update MR descriptions for all MRs in the project.

    --by=<gitlab-login>  Update MR descriptions for all MRs authored by the given GitLab user, where ``<gitlab-login>`` is the GitLab account name.

    --mine               Update MR descriptions for all MRs opened by the current user associated with the GitLab token.

    --related            Update MR descriptions for all MRs that are upstream and/or downstream of the MR for the current branch.
                         If ``machete.gitlab.mrDescriptionIntroStyle`` is ``up-only`` (default) or ``up-only-no-branches``, then only downstream MR descriptions are updated.
                         If ``machete.gitlab.mrDescriptionIntroStyle`` is ``full`` or ``full-no-branches``, then both downstream and upstream MR descriptions are updated.

**Git config keys:**

``machete.gitlab.{domain,remote,namespace,project}`` (all subcommands):
  .. include:: git-config-keys/gitlab_access.rst

``machete.gitlab.annotateWithUrls`` (all subcommands):
  .. include:: git-config-keys/gitlab_annotateWithUrls.rst

``machete.gitlab.forceDescriptionFromCommitMessage`` (``create-mr`` only):
  .. include:: git-config-keys/gitlab_forceDescriptionFromCommitMessage.rst

``machete.gitlab.mrDescriptionIntroStyle`` (``create-mr``, ``restack-mr`` and ``retarget-mr``):
  .. include:: git-config-keys/gitlab_mrDescriptionIntroStyle.rst

**Environment variables (all subcommands):**

``GITLAB_TOKEN``
    GitLab API token.
