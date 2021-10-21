.. _hooks:

hooks
-----
As with the standard git hooks, git machete looks for its own specific hooks in ``$GIT_DIR/hooks/*`` (or ``$(git config core.hooksPath)/*``, if set).

Note: ``hooks`` is not a command as such, just a help topic (there is no ``git machete hooks`` command).

* ``machete-post-slide-out <new-upstream> <lowest-slid-out-branch> [<new-downstreams>...]``

    The hook that is executed after a branch (or possibly multiple branches, in case of ``slide-out``)
    is slid out by ``advance``, ``slide-out`` or ``traverse``.

    At least two parameters (branch names) are passed to the hook:

        * <new-upstream> is the upstream of the branch that has been slid out, or in case of multiple branches being slid out --- the upstream of the highest slid out branch;
        * <lowest-slid-out-branch> is the branch that has been slid out, or in case of multiple branches being slid out --- the lowest slid out branch;
        * <new-downstreams> are all the following (possibly zero) parameters, which correspond to all original downstreams of <lowest-slid-out-branch>, now reattached as the downstreams of <new-upstream>.

    Note that this may be zero, one, or multiple branches.

    Note: the hook, if present, is executed:

        * zero or once during a ``advance`` execution (depending on whether the slide-out has been confirmed or not),
        * exactly once during a ``slide-out`` execution (even if multiple branches are slid out),
        * zero or more times during ``traverse`` (every time a slide-out operation is confirmed).

    If the hook returns a non-zero exit code, then an error is raised and the execution of the command is aborted,
    i.e. ``slide-out`` won't attempt rebase of the new downstream branches and ``traverse`` won't continue the traversal.
    In case of ``advance`` there is no difference (other than exit code of the entire ``advance`` command being non-zero),
    since slide-out is the last operation that happens within ``advance``.

    Note that non-zero exit code of the hook doesn't cancel the effects of slide-out itself, only the subsequent operations.
    The hook is executed only once the slide-out is complete and can in fact rely on .git/machete file being updated to the new branch layout.

* ``machete-pre-rebase <new-base> <fork-point-hash> <branch-being-rebased>``

    The hook that is executed before rebase is run during ``reapply``, ``slide-out``, ``traverse`` and ``update``.
    Note that it is NOT executed by ``squash`` (despite its similarity to ``reapply``), since no rebase is involved in ``squash``.

    The parameters are exactly the three revisions that are passed to ``git rebase --onto``:

        1. what is going to be the new base for the rebased commits,
        2. what is the fork point --- the place where the rebased history diverges from the upstream history,
        3. what branch is rebased.

    If the hook returns a non-zero exit code, the entire rebase is aborted.

    Note: this hook is independent from git's standard ``pre-rebase hook``.
    If machete-pre-rebase returns zero, the execution flow continues to ``git rebase``, which may also run ``pre-rebase hook`` if present.
    ``machete-pre-rebase`` is thus always launched before ``pre-rebase``.

* ``machete-status-branch <branch-name>``

    The hook that is executed for each branch displayed during ``discover``, ``status`` and ``traverse``.

    The standard output of this hook is displayed at the end of the line, after branch name, (optionally) custom annotation and (optionally) remote sync-ness status.
    Standard error is ignored. If the hook returns a non-zero exit code, both stdout and stderr are ignored, and printing the status continues as usual.

    Note: the hook is always invoked with ``ASCII_ONLY`` variable passed into the environment.
    If ``status`` runs in ASCII-only mode (i.e. if ``--color=auto`` and stdout is not a terminal, or if ``--color=never``), then ``ASCII_ONLY=true``, otherwise ``ASCII_ONLY=false``.

Please see `hook_samples <https://github.com/VirtusLab/git-machete/tree/master/hook_samples>`_ for examples.
An example of using the standard git ``post-commit hook`` to ``git machete add`` branches automatically is also included.
