.. _add:

add
---
**Usage:**

.. code-block:: shell

    git machete add [-o|--onto=<target-upstream-branch>] [-R|--as-root] [-y|--yes] [<branch>]

Adds the provided <branch> (or the current branch, if none specified) to the definition file.
If <branch> is provided but no local branch with the given name exists:

    * if a remote branch of the same name exists in exactly one remote, then user is asked whether to check out this branch locally (as in ``git checkout``),
    * otherwise, user is asked whether it should be created as a new local branch.

If the definition file is empty or ``-R/--as-root`` is provided, the branch will be added as a root of the tree of branch dependencies.
Otherwise, the desired upstream (parent) branch can be specified with ``-o/--onto``.
Neither of these options is mandatory, however; if both are skipped, git machete will try to automatically infer the target upstream.
If the upstream branch can be inferred, the user will be presented with inferred branch and asked to confirm.

Note: all the effects of ``add`` (except git branch creation) can as well be achieved by manually editing the definition file.

**Options:**

-o, --onto=<target-upstream-branch>    Specifies the target parent branch to add the given branch onto. Cannot be specified together with ``-R/--as-root``.

-R, --as-root                          Add the given branch as a new root (and not onto any other branch). Cannot be specified together with ``-o/--onto``.

-y, --yes                              Don't ask for confirmation whether to create the branch or whether to add onto the inferred upstream.
