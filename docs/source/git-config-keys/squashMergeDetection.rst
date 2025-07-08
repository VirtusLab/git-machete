Controls the algorithm used to detect squash merges. Possible values are:

* ``none``: Fastest mode, with no squash merge/rebase detection. Only *strict* (fast-forward or 2-parent) merges are detected.

* ``simple`` (default): Compares the tree (files & directories in the commit) of the downstream branch with the trees of the upstream branch.
  This detects squash merges/rebases as long as there exists a squash/rebase commit in the upstream that has the identical tree to what's in the downstream branch.

* ``exact``: Compares the patch (diff introduced by the commits) of the downstream branch with the patches of the upstream branch.
  This detects squash merges in more cases than ``simple`` mode.
  However, it might have a significant performance impact on large repositories as it requires computing patches for commits in the upstream branch.

This has an impact on:

* whether a grey edge is displayed in ``status``,
* whether ``traverse`` suggests to slide out the branch.
