``machete.github.domain``
    The domain of the GitHub API server, for use with GitHub Enterprise; otherwise inferred from the remote URL.
    For example, ``git config machete.github.domain git.example.org``

``machete.github.remote``
    The name of the git remote (as in ``git remote``) that git-machete pushes the head branch to.
    Unless both ``machete.github.organization`` and ``machete.github.repository`` are set, this remote's URL is also inspected
    to derive the GitHub organization and repository that the pull request resides in.
    The pull request is operated on through the GitHub API, which addresses that organization/repository rather than a git remote.
    By default (when this key is unset), if exactly one remote's URL corresponds to GitHub, that remote is selected automatically;
    set this key to disambiguate when more than one remote points to GitHub.
    For example, ``git config machete.github.remote origin``

``machete.github.organization``
    The GitHub organization (the part before ``/`` in ``organization/repository``); otherwise inferred from the remote URL.
    For example, ``git config machete.github.organization VirtusLab``

``machete.github.repository``
    The GitHub repository (the part after ``/`` in ``organization/repository``); otherwise inferred from the remote URL.
    For example, ``git config machete.github.repository git-machete``

Note that you do **not** need to set all four keys at once.
For example, in a typical usage of GitHub Enterprise, it should be enough to just set ``machete.github.domain``.
Only ``machete.github.organization`` and ``machete.github.repository`` must be specified together.
