``machete.gitlab.domain``
    The domain of the GitLab API server, for use with a GitLab self-managed instance; otherwise inferred from the remote URL.
    For example, ``git config machete.gitlab.domain git.example.org``

``machete.gitlab.remote``
    The name of the git remote (as in ``git remote``) that git-machete pushes the source branch to.
    Unless both ``machete.gitlab.namespace`` and ``machete.gitlab.project`` are set, this remote's URL is also inspected
    to derive the GitLab namespace and project that the merge request resides in.
    The merge request is operated on through the GitLab API, which addresses that namespace/project rather than a git remote.
    By default (when this key is unset), if exactly one remote's URL corresponds to GitLab, that remote is selected automatically;
    set this key to disambiguate when more than one remote points to GitLab.
    For example, ``git config machete.gitlab.remote origin``

``machete.gitlab.namespace``
    The GitLab namespace (the part before the final ``/`` in ``namespace/project``); otherwise inferred from the remote URL.
    For example, ``git config machete.gitlab.namespace foo/bar``

``machete.gitlab.project``
    The GitLab project (the part after the final ``/`` in ``namespace/project``); otherwise inferred from the remote URL.
    For example, ``git config machete.gitlab.project hello-world``

``machete.gitlab.baseRemote``
    Like ``machete.gitlab.remote``, but used to locate the target project that the merge request targets,
    which may differ from the source project (for example, the target in an upstream project and the source in a fork).
    Defaults to ``machete.gitlab.remote`` when unset.
    For example, ``git config machete.gitlab.baseRemote upstream``

``machete.gitlab.baseNamespace``
    Like ``machete.gitlab.namespace``, but for the target project that the merge request targets.
    Unless both this key and ``machete.gitlab.baseProject`` are set, the target namespace and project are derived
    from the URL of ``machete.gitlab.baseRemote``; there is no fall back to ``machete.gitlab.namespace``.
    Must be set together with ``machete.gitlab.baseProject``.
    For example, ``git config machete.gitlab.baseNamespace foo/bar``

``machete.gitlab.baseProject``
    Like ``machete.gitlab.project``, but for the target project that the merge request targets.
    Unless both this key and ``machete.gitlab.baseNamespace`` are set, the target namespace and project are derived
    from the URL of ``machete.gitlab.baseRemote``; there is no fall back to ``machete.gitlab.project``.
    Must be set together with ``machete.gitlab.baseNamespace``.
    For example, ``git config machete.gitlab.baseProject hello-world``

Note that you do **not** need to set all four keys at once.
For example, in a typical usage for GitLab self-managed instance, it should be enough to just set ``machete.gitlab.domain``.
Only ``machete.gitlab.namespace`` and ``machete.gitlab.project`` must be specified together,
as must ``machete.gitlab.baseNamespace`` and ``machete.gitlab.baseProject``.
