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

``machete.github.baseRemote``
    Like ``machete.github.remote``, but used to locate the base repository that the pull request targets,
    which may differ from the head repository (for example, the base in an upstream repository and the head in a fork).
    Defaults to ``machete.github.remote`` when unset.
    For example, ``git config machete.github.baseRemote upstream``

``machete.github.baseOrganization``
    Like ``machete.github.organization``, but for the base repository that the pull request targets.
    Unless both this key and ``machete.github.baseRepository`` are set, the base organization and repository are derived
    from the URL of ``machete.github.baseRemote``; there is no fall back to ``machete.github.organization``.
    Must be set together with ``machete.github.baseRepository``.
    For example, ``git config machete.github.baseOrganization VirtusLab``

``machete.github.baseRepository``
    Like ``machete.github.repository``, but for the base repository that the pull request targets.
    Unless both this key and ``machete.github.baseOrganization`` are set, the base organization and repository are derived
    from the URL of ``machete.github.baseRemote``; there is no fall back to ``machete.github.repository``.
    Must be set together with ``machete.github.baseOrganization``.
    For example, ``git config machete.github.baseRepository git-machete``

Note that you do **not** need to set all four keys at once.
For example, in a typical usage of GitHub Enterprise, it should be enough to just set ``machete.github.domain``.
Only ``machete.github.organization`` and ``machete.github.repository`` must be specified together,
as must ``machete.github.baseOrganization`` and ``machete.github.baseRepository``.
