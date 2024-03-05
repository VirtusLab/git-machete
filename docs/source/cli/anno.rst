.. _anno:

anno
====
**Usage:**

.. code-block:: shell

    git machete anno [-b|--branch=<branch>] [<annotation text>]
    git machete anno -H|--sync-github-prs
    git machete anno -L|--sync-gitlab-mrs

If invoked without any <annotation text>, prints out the custom annotation for the given branch
(or current branch, if none specified with ``-b/--branch``).

If invoked with a single empty string <annotation text>, like:

.. code-block:: shell

    $ git machete anno ''

then clears the annotation for the current branch (or a branch specified with ``-b/--branch``).

If invoked with ``-H``/``--sync-github-prs`` (for GitHub) or ``-L``/``--sync-gitlab-mrs`` (for GitLab),
annotates the branches based on their corresponding GitHub PR/GitLab MR numbers and authors.
When the current user is NOT the author of the PR/MR associated with that branch, adds ``rebase=no push=no`` branch qualifiers used by ``git machete traverse``,
so that you don't rebase or push someone else's PR/MR by accident (see help for :ref:`traverse`).
Any existing annotations (except branch qualifiers) are overwritten for the branches that have an opened PR/MR;
annotations for the other branches remain untouched.

.. note::

  See the help for :ref:`github` for how to configure GitHub API access.
  TL;DR: ``GITHUB_TOKEN`` env var or ``~/.github-token`` file or ``gh``/``hub`` CLI configs if exist.

  See the help for :ref:`gitlab` for how to configure GitLab API access.
  TL;DR: ``GITLAB_TOKEN`` env var or ``~/.gitlab-token`` file or ``glab`` CLI config if exists.

  For enterprise domains, non-standard URLs etc., check git config keys in either command's help.

In any other case, sets the annotation for the given/current branch to the given <annotation text>.
If multiple <annotation text>'s are passed to the command, they are concatenated with a single space.

Note: ``anno`` command is able to overwrite the existing branch qualifiers, for example with ``git machete anno "rebase=no push=no"``.

Note: all the effects of ``anno`` can be always achieved by manually editing the branch layout file.

**Options:**

-b, --branch=<branch>     Branch to set the annotation for.

-H, --sync-github-prs     Annotate with GitHub PR numbers and author logins where applicable.

-L, --sync-gitlab-mrs     Annotate with GitLab MR numbers and author logins where applicable.
