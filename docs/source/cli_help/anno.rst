.. _anno:

anno
----
**Usage:**

.. code-block:: shell

    git machete anno [-b|--branch=<branch>] [<annotation text>]
    git machete anno -H|--sync-github-prs

If invoked without any <annotation text>, prints out the custom annotation for the given branch (or current branch, if none specified with ``-b/--branch``).

If invoked with a single empty string <annotation text>, like:

.. code-block:: shell

    $ git machete anno ''

then clears the annotation for the current branch (or a branch specified with ``-b/--branch``).

If invoked with ``-H`` or ``--sync-github-prs``, annotates the branches based on their corresponding GitHub PR numbers and authors.
Any existing annotations are overwritten for the branches that have an opened PR; annotations for the other branches remain untouched.

To allow GitHub API access for private repositories (and also to perform side-effecting actions like opening a PR, even in case of public repositories),
a GitHub API token with ``repo`` scope is required, see https://github.com/settings/tokens. This will be resolved from the first of:

    1. ``GITHUB_TOKEN`` env var,
    2. content of the ``.github-token`` file in the home directory (``~``),
    2. current auth token from the ``gh`` GitHub CLI,
    3. current auth token from the ``hub`` GitHub CLI.

In any other case, sets the annotation for the given/current branch to the given <annotation text>.
If multiple <annotation text>'s are passed to the command, they are concatenated with a single space.

Note: all the effects of ``anno`` can be always achieved by manually editing the definition file.

**Options:**

-b, --branch=<branch>     Branch to set the annotation for.

-H, --sync-github-prs     Annotate with GitHub PR numbers and authors where applicable.

**Environment variables:**

``GITHUB_TOKEN``
    GitHub API token.
