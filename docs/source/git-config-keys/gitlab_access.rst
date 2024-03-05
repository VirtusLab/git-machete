GitLab API server URL will be inferred from ``git remote``.
You can alter the default behavior by setting the following git config keys:

    GitLab self-managed domain
        E.g. ``git config machete.gitlab.domain git.example.org``

    Remote name (as in ``git remote``)
        E.g. ``git config machete.gitlab.remote origin``

    Namespace and project name
        E.g. ``git config machete.gitlab.namespace foo/bar; git config machete.gitlab.project hello-world``

Note that you do **not** need to set all four keys at once.
For example, in a typical usage for GitLab self-managed instance, it should be enough to just set ``machete.gitlab.domain``.
Only ``machete.gitlab.namespace`` and ``machete.gitlab.project`` must be specified together.

..
    Text order in this file is relevant, if you want to change something, find each occurrence of ``.. include:: git-config-keys/gitlab_access.rst``
    and if this occurrence has ``start-line`` or ``end-line`` options provided, make sure that after changes the output text stays the same.
