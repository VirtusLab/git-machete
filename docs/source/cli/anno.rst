.. _anno:

anno
====
**Usage:**

.. code-block:: shell

    git machete anno [-b|--branch=<branch>] [<annotation text>]
    git machete anno -H|--sync-github-prs

If invoked without any <annotation text>, prints out the custom annotation for the given branch
(or current branch, if none specified with ``-b/--branch``).

If invoked with a single empty string <annotation text>, like:

.. code-block:: shell

    $ git machete anno ''

then clears the annotation for the current branch (or a branch specified with ``-b/--branch``).

If invoked with ``-H`` or ``--sync-github-prs``, annotates the branches based on their corresponding GitHub PR numbers and authors.
When the current user is **not** the owner of the PR associated with that branch, adds ``rebase=no push=no`` branch qualifiers used by ``git machete traverse``,
so that you don't rebase or push someone else's PR by accident (see help for :ref:`traverse`).
Any existing annotations (except branch qualifiers) are overwritten for the branches that have an opened PR; annotations for the other branches remain untouched.

.. include:: github_api_access.rst
.. include:: github_config_keys.rst

In any other case, sets the annotation for the given/current branch to the given <annotation text>.
If multiple <annotation text>'s are passed to the command, they are concatenated with a single space.

Note: ``anno`` command is able to overwrite existing branch qualifiers.

Note: all the effects of ``anno`` can be always achieved by manually editing the definition file.

**Options:**

-b, --branch=<branch>     Branch to set the annotation for.

-H, --sync-github-prs     Annotate with GitHub PR numbers and authors where applicable.

**Environment variables:**

``GITHUB_TOKEN``
    GitHub API token.
