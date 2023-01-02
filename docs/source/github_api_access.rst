.. note::

    To allow GitHub API access for private repositories (and also to perform side-effecting actions like opening a PR,
    even in case of public repositories), a GitHub API token with ``repo`` scope is required, see https://github.com/settings/tokens.
    This will be resolved from the first of:

        1. ``GITHUB_TOKEN`` env var,
        2. content of the ``.github-token`` file in the home directory (``~``),
        3. current auth token from the ``gh`` GitHub CLI,
        4. current auth token from the ``hub`` GitHub CLI.

    GitHub Enterprise domains are supported.

    ``GITHUB_TOKEN`` is used indiscriminately for any domain, both github.com and Enterprise.

    ``gh`` and ``hub`` have their own built-in support for Enterprise domains, which is honored by git-machete.

    ``.github-token`` can have multiple per-domain entries in the format:

      .. code-block::

        ghp_mytoken_for_github_com
        ghp_myothertoken_for_git_example_org git.example.org
        ghp_yetanothertoken_for_git_example_com git.example.com
