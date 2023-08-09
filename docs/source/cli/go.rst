.. _go:

go
==
**Usage:**

.. code-block:: shell

    git machete g[o] <direction>

where <direction> is one of: ``d[own]``, ``f[irst]``, ``l[ast]``, ``n[ext]``, ``p[rev]``, ``r[oot]``, ``u[p]``

Checks out the branch specified by the given direction relative to the current branch:

    * ``down``:    the direct children/downstream branch of the current branch.
    * ``first``:   the first downstream of the root branch of the current branch (like ``root`` followed by ``next``),
      or the root branch itself if the root has no downstream branches.
    * ``last``:    the last branch in the branch layout file that has the same root as the current branch;
      can be the root branch itself if the root has no downstream branches.
    * ``next``:    the direct successor of the current branch in the branch layout file.
    * ``prev``:    the direct predecessor of the current branch in the branch layout file.
    * ``root``:    the root of the tree where the current branch is located.
      Note: this will typically be something like ``develop`` or ``master``,
      since all branches are usually meant to be ultimately merged to one of those.
    * ``up``:      the direct parent/upstream branch of the current branch.

Roughly equivalent to ``git checkout $(git machete show <direction>)``.
