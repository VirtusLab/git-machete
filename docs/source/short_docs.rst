.. _short_docs:

* :ref:`add`              -- Add a branch to the tree of branch dependencies
* :ref:`advance`          -- Fast-forward merge one of children to the current branch, push it and then slide out the child
* :ref:`anno`             -- Manage custom annotations
* :ref:`clean`            -- Delete untracked and unmanaged branches and also optionally check out user's open GitHub PRs
* :ref:`config`           -- Display docs for the git machete configuration keys and environment variables
* :ref:`delete-unmanaged` -- Delete local branches that are not present in the branch layout file
* :ref:`diff`             -- Diff current working directory or a given branch against its computed fork point
* :ref:`discover`         -- Automatically discover tree of branch dependencies
* :ref:`edit`             -- Edit the branch layout file
* :ref:`file`             -- Display the location of the branch layout file
* :ref:`fork-point`       -- Display or override fork point for a branch
* :ref:`format`           -- Display docs for the format of the branch layout file
* :ref:`github`           -- Create, check out and manage GitHub PRs while keeping them reflected in git machete
* :ref:`go`               -- Check out the branch relative to the position of the current branch, accepts down/first/last/next/root/prev/up argument
* :ref:`help`             -- Display this overview, or detailed help for a specified command
* :ref:`hooks`            -- Display docs for the extra hooks added by git machete
* :ref:`is-managed`       -- Check if the current branch is managed by git machete (mostly for scripts)
* :ref:`list`             -- List all branches that fall into one of pre-defined categories (mostly for internal use)
* :ref:`log`              -- Log the part of history specific to the given branch
* :ref:`reapply`          -- Rebase the current branch onto its computed fork point
* :ref:`show`             -- Show name(s) of the branch(es) relative to the position of a branch, accepts down/first/last/next/root/prev/up argument
* :ref:`slide-out`        -- Slide out the current branch and sync its downstream (child) branches with its upstream (parent) branch via rebase or merge
* :ref:`squash`           -- Squash the unique history of the current branch into a single commit
* :ref:`status`           -- Display formatted tree of branch dependencies, including info on their sync with upstream branch and with remote
* :ref:`traverse`         -- Walk through the tree of branch dependencies and rebase, merge, slide out, push and/or pull each branch one by one. By default starts from current branch
* :ref:`update`           -- Sync the current branch with its upstream (parent) branch via rebase or merge
* :ref:`version`          -- Display the version and exit
