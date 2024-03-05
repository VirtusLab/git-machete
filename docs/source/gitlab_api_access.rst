.. note::

    To allow GitLab API access for private repositories (and also to perform side-effecting actions like opening a PR,
    even in case of public repositories), a GitLab API token with ``repo`` scope is required, see https://gitlab.com/settings/tokens.
    This will be resolved from the first of:

        1. ``GITLAB_TOKEN`` env var,
        2. content of the ``.gitlab-token`` file in the home directory (``~``),
        3. current auth token from the ``glab`` GitLab CLI.

    GitLab Enterprise domains are supported.

    ``GITLAB_TOKEN`` is used indiscriminately for any domain, both gitlab.com and Enterprise.

    ``glab`` has its own built-in support for Enterprise domains, which is honored by git-machete.

    ``.gitlab-token`` can have multiple per-domain entries in the format:

      .. code-block::

        glpat-mytoken_for_gitlab_com
        glpat-myothertoken_for_git_example_org git.example.org
        glpat-yetanothertoken_for_git_example_com git.example.com
