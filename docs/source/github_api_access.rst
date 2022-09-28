 .. note::

    To allow GitHub API access for private repositories (and also to perform side-effecting actions like opening a PR,
    even in case of public repositories), a GitHub API token with ``repo`` scope is required, see https://github.com/settings/tokens.
    This will be resolved from the first of:

        1. ``GITHUB_TOKEN`` env var,
        2. content of the ``.github-token`` file in the home directory (``~``),
        3. current auth token from the ``gh`` GitHub CLI,
        4. current auth token from the ``hub`` GitHub CLI.
