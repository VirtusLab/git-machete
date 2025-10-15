.. _show:

show
====
**Usage:**

.. code-block:: shell

    git machete show <direction> [<branch>]

where <direction> is one of: ``c[urrent]``, ``d[own]``, ``f[irst]``, ``l[ast]``, ``n[ext]``, ``p[rev]``, ``r[oot]``, ``u[p]``
displayed relative to given <branch>, or the current checked out branch if <branch> is unspecified.

Print name of the branch (or possibly multiple branches, in case of ``down``) that is:

* ``current``: the current branch; exits with a non-zero status if none (detached HEAD)

* ``down``:    the direct children/downstream branch of the given branch.

* ``first``:   the first downstream of the root branch of the given branch (like ``root`` followed by ``next``),
  or the root branch itself if the root has no downstream branches.

* ``last``:    the last branch in the branch layout file that has the same root as the given branch; can be the root branch itself
  if the root has no downstream branches.

* ``next``:    the direct successor of the given branch in the branch layout file.

* ``prev``:    the direct predecessor of the given branch in the branch layout file.

* ``root``:    the root of the tree where the given branch is located.
  Note: this will typically be something like ``develop`` or ``master``,
  since all branches are usually meant to be ultimately merged to one of those.

* ``up``:      the direct parent/upstream branch of the given branch.
