from typing import Dict

# ---------------------------------------------------------------------------------------------------------
# This file is supposed to be modified manually
# ---------------------------------------------------------------------------------------------------------

short_docs: Dict[str, str] = {
    "add": "Add a branch to the tree of branch dependencies",
    "advance": "Fast-forward merge one of children to the current branch, push it and then slide out the child",
    "anno": "Manage custom annotations",
    "clean": "Delete untracked and unmanaged branches and also optionally check out user's open GitHub PRs",
    "config": "Display docs for the git machete configuration keys and environment variables",
    "delete-unmanaged": "Delete local branches that are not present in the definition file",
    "diff": "Diff current working directory or a given branch against its computed fork point",
    "discover": "Automatically discover tree of branch dependencies",
    "edit": "Edit the definition file",
    "file": "Display the location of the definition file",
    "fork-point": "Display or override fork point for a branch",
    "format": "Display docs for the format of the definition file",
    "github": "Create, check out and manage GitHub PRs while keeping them reflected in git machete",
    "go": "Check out the branch relative to the position of the current branch, accepts down/first/last/next/root/prev/up argument",
    "help": "Display this overview, or detailed help for a specified command",
    "hooks": "Display docs for the extra hooks added by git machete",
    "is-managed": "Check if the current branch is managed by git machete (mostly for scripts)",
    "list": "List all branches that fall into one of pre-defined categories (mostly for internal use)",
    "log": "Log the part of history specific to the given branch",
    "reapply": "Rebase the current branch onto its computed fork point",
    "show": "Show name(s) of the branch(es) relative to the position of a branch, accepts down/first/last/next/root/prev/up argument",
    "slide-out": "Slide out the current branch and sync its downstream (child) branches with its upstream (parent) branch via rebase or merge",
    "squash": "Squash the unique history of the current branch into a single commit",
    "status": "Display formatted tree of branch dependencies, including info on their sync with upstream branch and with remote",
    "traverse": "Walk through the tree of branch dependencies and rebase, merge, slide out, push and/or pull each branch one by one. By default starts from current branch",
    "update": "Sync the current branch with its upstream (parent) branch via rebase or merge",
    "version": "Display the version and exit"
}
