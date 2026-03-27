"""MCP (Model Context Protocol) server for git-machete.

Implements a minimal JSON-RPC 2.0 over stdio server, exposing git-machete
commands as MCP tools. Uses only the Python standard library.
"""

import io
import json
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Callable, Dict, List, Optional, TextIO, Tuple

from git_machete import __version__, dispatch, utils
from git_machete.code_hosting import CodeHostingSpec
from git_machete.config import SquashMergeDetection
from git_machete.git_operations import (AnyRevision, GitContext,
                                        LocalBranchShortName)
from git_machete.github import GITHUB_CLIENT_SPEC
from git_machete.gitlab import GITLAB_CLIENT_SPEC
from git_machete.utils import MacheteException, UnderlyingGitException

_PROTOCOL_VERSION = "2024-11-05"


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

def _code_hosting_tool(
    *,
    tool_name: str,
    pr_or_mr: str,
    entity_name: str,
    platform: str,
) -> Dict[str, Any]:
    subcommands = [
        f"anno-{pr_or_mr}s",
        f"checkout-{pr_or_mr}s",
        f"create-{pr_or_mr}",
        f"restack-{pr_or_mr}",
        f"retarget-{pr_or_mr}",
        f"update-{pr_or_mr}-descriptions",
    ]
    return {
        "name": tool_name,
        "description": (
            f"Manage {platform} {entity_name}s in the context of the git machete branch tree. "
            f"Subcommands: "
            f"anno-{pr_or_mr}s (sync annotations to {entity_name}s), "
            f"checkout-{pr_or_mr}s (check out {entity_name} branches locally), "
            f"create-{pr_or_mr} (create a {entity_name} from current branch), "
            f"restack-{pr_or_mr} (update {entity_name} base to match parent branch), "
            f"retarget-{pr_or_mr} (change the base/target of a {entity_name}), "
            f"update-{pr_or_mr}-descriptions (update {entity_name} descriptions from branch layout)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "subcommand": {
                    "type": "string",
                    "enum": subcommands,
                    "description": f"The {platform} subcommand to run.",
                },
                "request_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": f"{entity_name} number(s). Used with checkout-{pr_or_mr}s.",
                },
                "all": {
                    "type": "boolean",
                    "description": f"Apply to all {entity_name}s. Used with checkout-{pr_or_mr}s, update-{pr_or_mr}-descriptions.",
                },
                "mine": {
                    "type": "boolean",
                    "description": f"Apply to my {entity_name}s only. Used with checkout-{pr_or_mr}s, update-{pr_or_mr}-descriptions.",
                },
                "by": {
                    "type": "string",
                    "description": f"Filter by author. Used with checkout-{pr_or_mr}s, update-{pr_or_mr}-descriptions.",
                },
                "branch": {
                    "type": "string",
                    "description": f"Target branch. Used with retarget-{pr_or_mr}.",
                },
                "base": {
                    "type": "string",
                    "description": f"Base branch for the {entity_name}. Used with create-{pr_or_mr}.",
                },
                "draft": {
                    "type": "boolean",
                    "description": f"Create as draft. Used with create-{pr_or_mr}.",
                },
                "title": {
                    "type": "string",
                    "description": f"Title for the {entity_name}. Used with create-{pr_or_mr}.",
                },
                "with_urls": {
                    "type": "boolean",
                    "description": f"Include URLs in annotations. Used with anno-{pr_or_mr}s.",
                },
                "ignore_if_missing": {
                    "type": "boolean",
                    "description": f"Don't fail if {entity_name} is missing. Used with retarget-{pr_or_mr}.",
                },
                "related": {
                    "type": "boolean",
                    "description": f"Apply to related {entity_name}s. Used with update-{pr_or_mr}-descriptions.",
                },
                "update_related_descriptions": {
                    "type": "boolean",
                    "description": (
                        f"Also update descriptions of related {entity_name}s. "
                        f"Used with create-{pr_or_mr}, restack-{pr_or_mr}, retarget-{pr_or_mr}."
                    ),
                },
            },
            "required": ["subcommand"],
        },
    }


_MCP_TOOL_META = Callable[[], Dict[str, Any]]
_MCP_TOOL_HANDLER = Callable[[GitContext, Dict[str, Any]], None]


def _dispatch_code_hosting(git: GitContext, spec: CodeHostingSpec, a: Dict[str, Any]) -> None:
    pr_or_mr = spec.pr_short_name.lower()
    subcommand = a["subcommand"]

    if subcommand == f"anno-{pr_or_mr}s":
        dispatch.code_hosting_anno_prs(git, spec, include_urls=bool(a.get("with_urls")))
    elif subcommand == f"checkout-{pr_or_mr}s":
        dispatch.code_hosting_checkout_prs(
            git, spec,
            pr_numbers=a.get("request_ids") or [],
            opt_all=bool(a.get("all")),
            opt_mine=bool(a.get("mine")),
            opt_by=a.get("by"))
    elif subcommand == f"create-{pr_or_mr}":
        base = LocalBranchShortName.of(a["base"]) if a.get("base") else None
        dispatch.code_hosting_create_pr(
            git, spec,
            opt_base=base,
            opt_draft=bool(a.get("draft")),
            opt_title=a.get("title"),
            opt_update_related_descriptions=bool(a.get("update_related_descriptions")),
            opt_yes=True)
    elif subcommand == f"restack-{pr_or_mr}":
        dispatch.code_hosting_restack_pr(
            git, spec,
            opt_update_related_descriptions=bool(a.get("update_related_descriptions")))
    elif subcommand == f"retarget-{pr_or_mr}":
        branch = LocalBranchShortName.of(a["branch"]) if a.get("branch") else git.get_current_branch()
        dispatch.code_hosting_retarget_pr(
            git, spec,
            branch=branch,
            opt_ignore_if_missing=bool(a.get("ignore_if_missing")),
            opt_update_related_descriptions=bool(a.get("update_related_descriptions")))
    elif subcommand == f"update-{pr_or_mr}-descriptions":
        dispatch.code_hosting_update_pr_descriptions(
            git, spec,
            opt_all=bool(a.get("all")),
            opt_by=a.get("by"),
            opt_mine=bool(a.get("mine")),
            opt_related=bool(a.get("related")))
    else:
        raise ValueError(f"Unknown subcommand: {subcommand}")


def _tool_spec_machete_add() -> Dict[str, Any]:
    return {
        "name": "machete_add",
        "description": (
            "Add a branch to the tree of branch dependencies. "
            "The branch can be added as a child of a given parent (--onto), as a new root, "
            "or by default as a child of the current branch."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch to add. Defaults to the current branch.",
                },
                "onto": {
                    "type": "string",
                    "description": "Make the added branch a child of this branch.",
                },
                "as_root": {
                    "type": "boolean",
                    "description": "Add as a new root (no parent) instead of as a child.",
                },
            },
        },
    }


def _run_machete_add(git: GitContext, a: Dict[str, Any]) -> None:
    branch = LocalBranchShortName.of(a["branch"]) if a.get("branch") else git.get_current_branch()
    onto = LocalBranchShortName.of(a["onto"]) if a.get("onto") else None
    dispatch.add(
        git,
        branch=branch,
        opt_onto=onto,
        opt_as_first_child=False,
        opt_as_root=bool(a.get("as_root")),
        opt_yes=True)


def _tool_spec_machete_advance() -> Dict[str, Any]:
    return {
        "name": "machete_advance",
        "description": (
            "Fast-forward merge one of the children of the current branch into the current branch, "
            "then push the current branch and slide out the child. "
            "Useful after a child branch has been merged/approved. "
            "Runs non-interactively (auto-selects the child if unambiguous)."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    }


def _run_machete_advance(git: GitContext, _a: Dict[str, Any]) -> None:
    dispatch.advance(git, opt_yes=True)


def _tool_spec_machete_anno() -> Dict[str, Any]:
    return {
        "name": "machete_anno",
        "description": (
            "Manage custom annotations for branches. "
            "Without annotation_text: display the annotation of the given branch. "
            "With annotation_text: set (or clear, if empty string) the annotation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "annotation_text": {
                    "type": "string",
                    "description": "Annotation text to set. Pass empty string to clear. Omit to display current annotation.",
                },
                "branch": {
                    "type": "string",
                    "description": "Target branch. Defaults to the current branch.",
                },
            },
        },
    }


def _run_machete_anno(git: GitContext, a: Dict[str, Any]) -> None:
    branch = LocalBranchShortName.of(a["branch"]) if a.get("branch") else git.get_current_branch()
    annotation_text_raw = a.get("annotation_text")
    dispatch.anno(
        git,
        branch=branch,
        annotation_text=[annotation_text_raw] if annotation_text_raw is not None else None,
        opt_sync_github_prs=False,
        opt_sync_gitlab_mrs=False,
        spec=GITHUB_CLIENT_SPEC)


def _tool_spec_machete_delete_unmanaged() -> Dict[str, Any]:
    return {
        "name": "machete_delete_unmanaged",
        "description": (
            "Delete local branches that are not present in the branch layout file. "
            "WARNING: this deletes branches. Runs non-interactively (auto-confirms)."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    }


def _run_machete_delete_unmanaged(git: GitContext, _a: Dict[str, Any]) -> None:
    dispatch.delete_unmanaged(git, opt_yes=True)


def _tool_spec_machete_diff() -> Dict[str, Any]:
    return {
        "name": "machete_diff",
        "description": (
            "Diff the current working directory or a given branch against its fork point. "
            "Shows only the changes introduced on the branch, excluding changes from the parent."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch to diff. Defaults to the current branch.",
                },
                "stat": {
                    "type": "boolean",
                    "description": "Show only a diffstat (file names and change counts) instead of full diff.",
                },
            },
        },
    }


def _run_machete_diff(git: GitContext, a: Dict[str, Any]) -> None:
    diff_branch = LocalBranchShortName.of(a["branch"]) if a.get("branch") else None
    dispatch.diff(git, branch=diff_branch, opt_stat=bool(a.get("stat")), extra_args=[])


def _tool_spec_machete_discover() -> Dict[str, Any]:
    return {
        "name": "machete_discover",
        "description": (
            "Automatically discover the tree of branch dependencies based on the "
            "current local branches and their relationships. "
            "Overwrites the current branch layout file. "
            "Runs non-interactively (auto-confirms)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "list_commits": {
                    "type": "boolean",
                    "description": "List commits introduced on each branch in the status output after discovery.",
                },
                "roots": {
                    "type": "string",
                    "description": "Comma-separated list of branches to use as roots of the discovered tree.",
                },
                "checked_out_since": {
                    "type": "string",
                    "description": "Only consider branches checked out at least once since this date (e.g. '2 weeks ago').",
                },
            },
        },
    }


def _run_machete_discover(git: GitContext, a: Dict[str, Any]) -> None:
    roots_str = a.get("roots")
    roots = [LocalBranchShortName.of(r) for r in roots_str.split(",") if r] if roots_str else []
    dispatch.discover(
        git,
        opt_checked_out_since=a.get("checked_out_since"),
        opt_list_commits=bool(a.get("list_commits")),
        opt_roots=roots,
        opt_yes=True)


def _tool_spec_machete_file() -> Dict[str, Any]:
    return {
        "name": "machete_file",
        "description": (
            "Display the absolute path of the branch layout file "
            "(usually .git/machete or .git/info/machete). "
            "This file defines the tree structure of managed branches."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    }


def _run_machete_file(git: GitContext, _a: Dict[str, Any]) -> None:
    dispatch.file(git)


def _tool_spec_machete_fork_point() -> Dict[str, Any]:
    return {
        "name": "machete_fork_point",
        "description": (
            "Display or override the fork point of a branch. "
            "The fork point is the commit where the branch's unique history begins "
            "(i.e., diverges from its parent). git machete uses heuristics based on reflogs "
            "to determine this. Deprecated CLI overrides (--override-to, --override-to-inferred) "
            "are not exposed here; use machete_update with fork_point to rebase onto a specific "
            "revision, or override_to_parent / unset_override for fork-point overrides."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch to inspect. Defaults to the current branch.",
                },
                "inferred": {
                    "type": "boolean",
                    "description": "Show the inferred fork point (ignoring any overrides).",
                },
                "override_to_parent": {
                    "type": "boolean",
                    "description": "Set the fork point override to the tip of the parent branch.",
                },
                "unset_override": {
                    "type": "boolean",
                    "description": "Remove any fork point override.",
                },
            },
        },
    }


def _run_machete_fork_point(git: GitContext, a: Dict[str, Any]) -> None:
    branch = LocalBranchShortName.of(a["branch"]) if a.get("branch") else git.get_current_branch()
    dispatch.fork_point(
        git,
        branch=branch,
        opt_inferred=bool(a.get("inferred")),
        opt_override_to_parent=bool(a.get("override_to_parent")),
        opt_unset_override=bool(a.get("unset_override")))


def _tool_spec_machete_github() -> Dict[str, Any]:
    return _code_hosting_tool(
        tool_name="machete_github",
        pr_or_mr="pr",
        entity_name="PR",
        platform="GitHub",
    )


def _run_machete_github(git: GitContext, a: Dict[str, Any]) -> None:
    _dispatch_code_hosting(git, GITHUB_CLIENT_SPEC, a)


def _tool_spec_machete_gitlab() -> Dict[str, Any]:
    return _code_hosting_tool(
        tool_name="machete_gitlab",
        pr_or_mr="mr",
        entity_name="MR",
        platform="GitLab",
    )


def _run_machete_gitlab(git: GitContext, a: Dict[str, Any]) -> None:
    _dispatch_code_hosting(git, GITLAB_CLIENT_SPEC, a)


def _tool_spec_machete_go() -> Dict[str, Any]:
    return {
        "name": "machete_go",
        "description": (
            "Check out the branch relative to the current branch's position in the tree. "
            "WARNING: this changes the currently checked-out branch in the working directory. "
            "Directions: 'up' (parent), 'down' (child), 'first' (first child), "
            "'last' (last child), 'next' (next sibling), 'prev' (previous sibling), 'root' (tree root)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "first", "last", "next", "prev", "root"],
                    "description": "The direction to navigate in the branch tree.",
                },
            },
            "required": ["direction"],
        },
    }


def _run_machete_go(git: GitContext, a: Dict[str, Any]) -> None:
    dispatch.go(git, direction=a["direction"])


def _tool_spec_machete_log() -> Dict[str, Any]:
    return {
        "name": "machete_log",
        "description": (
            "Log the commits unique to the given branch, i.e., the commits between "
            "the fork point and the branch tip. Equivalent to 'git log fork-point..branch'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch to log. Defaults to the current branch.",
                },
            },
        },
    }


def _run_machete_log(git: GitContext, a: Dict[str, Any]) -> None:
    branch = LocalBranchShortName.of(a["branch"]) if a.get("branch") else git.get_current_branch()
    dispatch.log(git, branch=branch, extra_args=[])


def _tool_spec_machete_reapply() -> Dict[str, Any]:
    return {
        "name": "machete_reapply",
        "description": (
            "Rebase the current branch onto its own fork point. "
            "Useful for cleaning up the branch's history without changing its base."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "fork_point": {
                    "type": "string",
                    "description": "Override the fork point revision for the rebase.",
                },
            },
        },
    }


def _run_machete_reapply(git: GitContext, a: Dict[str, Any]) -> None:
    fp = AnyRevision.of(a["fork_point"]) if a.get("fork_point") else None
    dispatch.reapply(git, opt_fork_point=fp, opt_no_interactive_rebase=True)


def _tool_spec_machete_show() -> Dict[str, Any]:
    return {
        "name": "machete_show",
        "description": (
            "Show the name(s) of branch(es) relative to a given branch's position in the tree. "
            "Directions: 'current' (current branch), 'up' (parent), 'down' (children), "
            "'first' (first child), 'last' (last child), 'next' (next sibling), "
            "'prev' (previous sibling), 'root' (root of the tree containing the branch)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["current", "up", "down", "first", "last", "next", "prev", "root"],
                    "description": "The direction to look in the branch tree.",
                },
                "branch": {
                    "type": "string",
                    "description": "The reference branch. Defaults to the current branch.",
                },
            },
            "required": ["direction"],
        },
    }


def _run_machete_show(git: GitContext, a: Dict[str, Any]) -> None:
    branch = LocalBranchShortName.of(a["branch"]) if a.get("branch") else git.get_current_branch()
    dispatch.show(git, direction=a["direction"], branch=branch)


def _tool_spec_machete_slide_out() -> Dict[str, Any]:
    return {
        "name": "machete_slide_out",
        "description": (
            "Slide out one or more branches from the tree: remove each from the layout and "
            "rebase its children onto its parent. "
            "Useful for removing intermediate branches after they've been merged. "
            "Runs non-interactively. "
            "Alternatively, with removed_from_remote=true, slide out every managed leaf branch "
            "whose remote-tracking branch no longer exists (same as "
            "`git machete slide-out --removed-from-remote`); in that mode only delete may be set."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "removed_from_remote": {
                    "type": "boolean",
                    "description": (
                        "Slide out managed branches that no longer exist on the remote (no downstream). "
                        "Cannot be combined with branches, merge, or no_rebase; only delete is allowed."
                    ),
                },
                "branches": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Branch(es) to slide out. Defaults to the current branch. Ignored if removed_from_remote is true.",
                },
                "delete": {
                    "type": "boolean",
                    "description": "Also delete the slid-out branches from git.",
                },
                "merge": {
                    "type": "boolean",
                    "description": "Use merge instead of rebase when moving children.",
                },
                "no_rebase": {
                    "type": "boolean",
                    "description": "Don't rebase children at all, just remove the branch from the layout.",
                },
            },
        },
    }


def _run_machete_slide_out(git: GitContext, a: Dict[str, Any]) -> None:
    if a.get("removed_from_remote"):
        extras = [k for k in ("branches", "merge", "no_rebase") if a.get(k)]
        if extras:
            raise ValueError(
                "Only `delete` may be set together with `removed_from_remote` "
                f"(remove: {', '.join(extras)})")
    branches_raw = a.get("branches") or []
    dispatch.slide_out(
        git,
        branches=[LocalBranchShortName.of(b) for b in branches_raw] if branches_raw else [git.get_current_branch()],
        opt_delete=bool(a.get("delete")),
        opt_down_fork_point=None,
        opt_merge=bool(a.get("merge")),
        opt_no_edit_merge=True,
        opt_no_interactive_rebase=not bool(a.get("merge")),
        opt_no_rebase=bool(a.get("no_rebase")),
        opt_removed_from_remote=bool(a.get("removed_from_remote")))


def _tool_spec_machete_squash() -> Dict[str, Any]:
    return {
        "name": "machete_squash",
        "description": (
            "Squash all unique commits on the current branch into a single commit. "
            "The commits between the fork point and HEAD are replaced by one commit "
            "with the combined changes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "fork_point": {
                    "type": "string",
                    "description": "Override the fork point revision for determining which commits to squash.",
                },
            },
        },
    }


def _run_machete_squash(git: GitContext, a: Dict[str, Any]) -> None:
    fp = AnyRevision.of(a["fork_point"]) if a.get("fork_point") else None
    dispatch.squash(git, opt_fork_point=fp)


def _tool_spec_machete_status() -> Dict[str, Any]:
    return {
        "name": "machete_status",
        "description": (
            "Display a tree-shaped status of branches managed by git machete. "
            "Each branch shows its sync relationship to its parent "
            "(in sync, out of sync, merged to parent) and to its remote tracking "
            "branch (ahead, behind, diverged, untracked). "
            "This is the primary tool for understanding the repository's branch structure."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "list_commits": {
                    "type": "boolean",
                    "description": "List short hashes and subjects of commits introduced on each branch.",
                },
                "list_commits_with_hashes": {
                    "type": "boolean",
                    "description": "Like list_commits but also includes full commit hashes.",
                },
            },
        },
    }


def _run_machete_status(git: GitContext, a: Dict[str, Any]) -> None:
    list_commits_with_hashes = bool(a.get("list_commits_with_hashes"))
    dispatch.status(
        git,
        opt_list_commits=bool(a.get("list_commits")) or list_commits_with_hashes,
        opt_list_commits_with_hashes=list_commits_with_hashes,
        opt_squash_merge_detection=SquashMergeDetection.SIMPLE)


def _tool_spec_machete_update() -> Dict[str, Any]:
    return {
        "name": "machete_update",
        "description": (
            "Update the current branch by rebasing (default) or merging it onto its "
            "parent branch as defined in the branch layout. "
            "Runs non-interactively (no interactive rebase editor) unless using merge."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "merge": {
                    "type": "boolean",
                    "description": "Use merge instead of rebase to incorporate parent's changes.",
                },
                "fork_point": {
                    "type": "string",
                    "description": "Override the fork point revision for the rebase.",
                },
            },
        },
    }


def _run_machete_update(git: GitContext, a: Dict[str, Any]) -> None:
    fp = AnyRevision.of(a["fork_point"]) if a.get("fork_point") else None
    is_merge = bool(a.get("merge"))
    dispatch.update(
        git,
        opt_merge=is_merge,
        opt_no_edit_merge=not is_merge,
        opt_no_interactive_rebase=not is_merge,
        opt_fork_point=fp)


_MCP_TOOLS: Dict[str, Tuple[_MCP_TOOL_META, _MCP_TOOL_HANDLER]] = dict(sorted((
    ("machete_add", (_tool_spec_machete_add, _run_machete_add)),
    ("machete_advance", (_tool_spec_machete_advance, _run_machete_advance)),
    ("machete_anno", (_tool_spec_machete_anno, _run_machete_anno)),
    ("machete_delete_unmanaged", (_tool_spec_machete_delete_unmanaged, _run_machete_delete_unmanaged)),
    ("machete_diff", (_tool_spec_machete_diff, _run_machete_diff)),
    ("machete_discover", (_tool_spec_machete_discover, _run_machete_discover)),
    ("machete_file", (_tool_spec_machete_file, _run_machete_file)),
    ("machete_fork_point", (_tool_spec_machete_fork_point, _run_machete_fork_point)),
    ("machete_github", (_tool_spec_machete_github, _run_machete_github)),
    ("machete_gitlab", (_tool_spec_machete_gitlab, _run_machete_gitlab)),
    ("machete_go", (_tool_spec_machete_go, _run_machete_go)),
    ("machete_log", (_tool_spec_machete_log, _run_machete_log)),
    ("machete_reapply", (_tool_spec_machete_reapply, _run_machete_reapply)),
    ("machete_show", (_tool_spec_machete_show, _run_machete_show)),
    ("machete_slide_out", (_tool_spec_machete_slide_out, _run_machete_slide_out)),
    ("machete_squash", (_tool_spec_machete_squash, _run_machete_squash)),
    ("machete_status", (_tool_spec_machete_status, _run_machete_status)),
    ("machete_update", (_tool_spec_machete_update, _run_machete_update)),
)))

assert all(
    n == meta()["name"]
    for n, (meta, _) in _MCP_TOOLS.items())

_TOOLS: List[Dict[str, Any]] = [meta() for _, (meta, _) in _MCP_TOOLS.items()]


def _dispatch_tool(tool_name: str, a: Dict[str, Any], git: GitContext) -> None:
    """Call the appropriate dispatch function for the given MCP tool."""
    pair = _MCP_TOOLS.get(tool_name)
    if pair is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    pair[1](git, a)


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _capturing_run_cmd(
    cmd: str,
    *args: str,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> int:
    """Replacement for utils._run_cmd that captures subprocess stdout/stderr
    and forwards them into the (redirected) sys.stdout / sys.stderr so that
    redirect_stdout/redirect_stderr can pick them up."""
    completed = subprocess.run(
        [cmd] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    sys.stdout.write(completed.stdout.decode("utf-8"))
    sys.stderr.write(completed.stderr.decode("utf-8"))
    return completed.returncode


def _execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool call via dispatch and return an MCP CallToolResult."""
    captured_out = io.StringIO()
    captured_err = io.StringIO()
    is_error = False
    error_message: Optional[str] = None

    old_stdin = sys.stdin
    old_run_cmd = utils._run_cmd
    old_use_ansi_stdout = utils.use_ansi_escapes_in_stdout
    old_use_ansi_stderr = utils.use_ansi_escapes_in_stderr
    sys.stdin = io.StringIO()
    utils._run_cmd = _capturing_run_cmd  # type: ignore[assignment]
    utils.use_ansi_escapes_in_stdout = False
    utils.use_ansi_escapes_in_stderr = False
    try:
        with redirect_stdout(captured_out), redirect_stderr(captured_err):
            utils.displayed_warnings = set()
            git = GitContext()
            try:
                _dispatch_tool(tool_name, arguments, git)
            except (MacheteException, UnderlyingGitException) as e:
                is_error = True
                error_message = str(e)
            except EOFError:
                is_error = True
                error_message = "This command requires interactive input, which is not available in MCP mode."
    finally:
        sys.stdin = old_stdin
        utils._run_cmd = old_run_cmd
        utils.use_ansi_escapes_in_stdout = old_use_ansi_stdout
        utils.use_ansi_escapes_in_stderr = old_use_ansi_stderr

    parts: List[str] = []
    stdout_text = captured_out.getvalue()
    stderr_text = captured_err.getvalue()
    if stdout_text:
        parts.append(stdout_text.rstrip("\n"))
    if stderr_text:
        parts.append(stderr_text.rstrip("\n"))
    if error_message:
        parts.append(error_message)

    text = "\n".join(parts) if parts else "(no output)"
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def _response(request_id: Any, *, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: Any, *, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------

def _handle_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process one JSON-RPC message.  Returns a response dict, or None for notifications."""
    request_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {})

    # Notifications (no id) don't get a response
    if request_id is None:
        return None

    if method == "initialize":
        return _response(request_id, result={
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "git-machete", "version": __version__},
        })

    if method == "ping":
        return _response(request_id, result={})

    if method == "tools/list":
        return _response(request_id, result={"tools": _TOOLS})

    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        if name not in _MCP_TOOLS:
            return _error_response(request_id, code=_INVALID_PARAMS, message=f"Unknown tool: {name}")
        try:
            result = _execute_tool(name, arguments)
        except Exception as e:
            result = {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            }
        return _response(request_id, result=result)

    if method == "resources/list":
        return _response(request_id, result={"resources": []})

    if method == "prompts/list":
        return _response(request_id, result={"prompts": []})

    return _error_response(request_id, code=_METHOD_NOT_FOUND, message=f"Method not found: {method}")


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def serve(
        *,
        stdin: Optional[TextIO] = None,
        stdout: Optional[TextIO] = None,
) -> None:
    """Run the MCP server, reading JSON-RPC messages from *stdin* and writing
    responses to *stdout*.  Accepts optional streams for testability;
    defaults to sys.stdin / sys.stdout.

    Lifecycle: the MCP client (IDE, agent host, etc.) owns this process. It
    normally stops the server by closing *stdin* and/or sending SIGTERM; the
    read loop then ends. This server does not expose a dedicated shutdown RPC."""
    _stdin: TextIO = stdin or sys.stdin
    _stdout: TextIO = stdout or sys.stdout

    def send(msg: Dict[str, Any]) -> None:
        _stdout.write(json.dumps(msg, separators=(",", ":")) + "\n")
        _stdout.flush()

    for line in _stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            send(_error_response(None, code=-32700, message="Parse error"))
            continue

        reply = _handle_message(msg)
        if reply is not None:
            send(reply)
