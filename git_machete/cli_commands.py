"""Catalog of git-machete CLI commands.

This module is pure data: it declares every command, alias, option,
positional, mutex group and subcommand that `git machete` understands.
The parsing engine that consumes these declarations lives in
`cli_parser.py`.

Keeping the catalog separate from the parser lets the parser stay
generic over its input (any catalog of the right shape works) and keeps
the two layers - "what the CLI accepts" vs. "how arguments are parsed"
- changing independently.
"""

from typing import Dict, Tuple

from git_machete.cli_parser import (CommandSpec, MutexGroup, OptSpec,
                                    PositionalSpec, SubcommandSpec)
from git_machete.help import commands_and_aliases


# ────────────────────────────────────────────────────────────────────────────
# Common options - accepted both before and after the command name.
# ────────────────────────────────────────────────────────────────────────────

COMMON_OPTIONS: Tuple[OptSpec, ...] = (
    OptSpec(long="debug"),
    OptSpec(short="h", long="help"),
    OptSpec(short="v", long="verbose"),
    OptSpec(long="version"),
)


# ────────────────────────────────────────────────────────────────────────────
# Command table
# ────────────────────────────────────────────────────────────────────────────


_GO_DIRECTION_CHOICES: Tuple[str, ...] = (
    "d", "down", "f", "first", "l", "last", "n", "next",
    "p", "prev", "r", "root", "u", "up",
)
_SHOW_DIRECTION_CHOICES: Tuple[str, ...] = ("c", "current") + _GO_DIRECTION_CHOICES


def _code_hosting_spec(*, command: str, pr_or_mr: str, include_sync: bool) -> CommandSpec:
    """github/gitlab share an identical surface modulo `sync` being deep into
    deprecation on github-only - build them from one mould.

    Each second-level subcommand owns its own options; the dispatcher in
    `cli.py` only needs to look up the selected subcommand and run its
    command-specific logic, because invalid combinations
    (`github anno-prs --draft`, `gitlab retarget-mr 123`, ...) are
    rejected by the parser before the dispatcher ever sees them.
    """
    subcommands: Tuple[SubcommandSpec, ...] = (
        SubcommandSpec(
            name=f"anno-{pr_or_mr}s",
            options=(OptSpec(long="with-urls"),),
        ),
        SubcommandSpec(
            name=f"checkout-{pr_or_mr}s",
            options=(
                OptSpec(long="all"),
                OptSpec(long="by", takes_value=True),
                OptSpec(long="mine"),
            ),
        ),
        SubcommandSpec(
            name=f"create-{pr_or_mr}",
            options=(
                # Intentionally undocumented (see commit 336c152): an escape
                # hatch for the rare case when the parent branch detected by
                # git-machete isn't the desired PR/MR base. Not exposed
                # anywhere user-facing on purpose.
                OptSpec(long="base", takes_value=True),
                OptSpec(long="draft"),
                OptSpec(long="title", takes_value=True),
                OptSpec(short="U", long="update-related-descriptions"),
                OptSpec(short="y", long="yes"),
            ),
        ),
        SubcommandSpec(
            name=f"restack-{pr_or_mr}",
            options=(OptSpec(short="U", long="update-related-descriptions"),),
        ),
        SubcommandSpec(
            name=f"retarget-{pr_or_mr}",
            options=(
                OptSpec(short="b", long="branch", takes_value=True),
                OptSpec(long="ignore-if-missing"),
                OptSpec(short="U", long="update-related-descriptions"),
            ),
        ),
        SubcommandSpec(
            name=f"update-{pr_or_mr}-descriptions",
            options=(
                OptSpec(long="all"),
                OptSpec(long="by", takes_value=True),
                OptSpec(long="mine"),
                OptSpec(long="related"),
            ),
        ),
    ) + ((SubcommandSpec(name="sync", hidden=True),) if include_sync else ())

    return CommandSpec(
        name=command,
        subcommands=subcommands,
        positionals=(
            PositionalSpec(
                name="request_id",
                display_name=f"{pr_or_mr.upper()} number",
                required=False,
                multiple=True,
                type_conv=int,
                only_with_subcommand=(f"checkout-{pr_or_mr}s",),
            ),
        ),
    )


COMMANDS: Tuple[CommandSpec, ...] = (
    CommandSpec(
        name="add",
        options=(
            OptSpec(short="f", long="as-first-child"),
            OptSpec(short="o", long="onto", takes_value=True),
            OptSpec(short="R", long="as-root"),
            OptSpec(short="y", long="yes"),
        ),
        mutex_groups=(
            MutexGroup(
                ("as-root", "onto"),
                "Option `-R/--as-root` cannot be specified together with `-o/--onto`."),
            MutexGroup(
                ("as-root", "as-first-child"),
                "Option `-R/--as-root` cannot be specified together with `-f/--as-first-child`."),
        ),
        positionals=(PositionalSpec(name="branch", required=False),),
    ),
    CommandSpec(
        name="advance",
        options=(OptSpec(short="y", long="yes"),),
    ),
    CommandSpec(
        name="anno",
        options=(
            OptSpec(short="b", long="branch", takes_value=True),
            OptSpec(short="H", long="sync-github-prs"),
            OptSpec(short="L", long="sync-gitlab-mrs"),
        ),
        mutex_groups=(MutexGroup(("sync-github-prs", "sync-gitlab-mrs")),),
        positionals=(
            # `nargs='*'`: possible values include [], [''], ['some_val'], ['t1', 't2']
            PositionalSpec(name="annotation_text", required=False, multiple=True),
        ),
    ),
    CommandSpec(
        name="clean",
        options=(
            OptSpec(short="H", long="checkout-my-github-prs"),
            OptSpec(short="y", long="yes"),
        ),
    ),
    CommandSpec(
        name="completion",
        # Shells we ship completion resource files for.
        positionals=(PositionalSpec(name="shell", choices=("bash", "fish", "zsh")),),
    ),
    CommandSpec(
        name="delete-unmanaged",
        options=(OptSpec(short="y", long="yes"),),
    ),
    CommandSpec(
        name="diff",
        aliases=("d",),
        options=(OptSpec(short="s", long="stat"),),
        positionals=(PositionalSpec(name="branch", required=False),),
    ),
    CommandSpec(
        name="discover",
        options=(
            OptSpec(short="C", long="checked-out-since", takes_value=True),
            OptSpec(short="l", long="list-commits"),
            OptSpec(short="r", long="roots", takes_value=True),
            OptSpec(short="y", long="yes"),
        ),
    ),
    CommandSpec(name="edit", aliases=("e",)),
    CommandSpec(name="file"),
    CommandSpec(
        name="fork-point",
        options=(
            OptSpec(long="explain"),
            OptSpec(long="inferred"),
            OptSpec(long="override-to", takes_value=True),
            OptSpec(long="override-to-inferred"),
            OptSpec(long="override-to-parent"),
            OptSpec(long="unset-override"),
        ),
        mutex_groups=(
            # Any two of these clobber each other (`--inferred` vs the
            # override-*/unset-override family is also covered).
            MutexGroup(("inferred", "override-to", "override-to-inferred",
                        "override-to-parent", "unset-override")),
            # `--explain` is informational and conflicts with anything that
            # MUTATES the fork-point override. Modelled as four pair groups
            # sharing the same custom message; only the first matching pair
            # fires (we exit on the first violation).
            *(
                MutexGroup(
                    ("explain", override_opt),
                    "`--explain` cannot be combined with "
                    "`--override-to`/`--override-to-inferred`/`--override-to-parent`/`--unset-override`.")
                for override_opt in (
                    "override-to", "override-to-inferred",
                    "override-to-parent", "unset-override")
            ),
        ),
        positionals=(PositionalSpec(name="branch", required=False),),
    ),
    _code_hosting_spec(command="github", pr_or_mr="pr", include_sync=True),
    _code_hosting_spec(command="gitlab", pr_or_mr="mr", include_sync=False),
    CommandSpec(
        name="go",
        aliases=("g",),
        positionals=(
            PositionalSpec(
                name="direction",
                display_name="go direction",
                required=False,
                choices=_GO_DIRECTION_CHOICES,
            ),
        ),
    ),
    CommandSpec(
        name="help",
        positionals=(
            PositionalSpec(
                name="topic_or_cmd",
                required=False,
                choices=tuple(commands_and_aliases),
            ),
        ),
    ),
    CommandSpec(
        name="is-managed",
        positionals=(PositionalSpec(name="branch", required=False),),
    ),
    CommandSpec(
        name="list",
        positionals=(
            PositionalSpec(
                name="category",
                choices=(
                    "addable", "childless", "managed", "slidable", "slidable-after",
                    "unmanaged", "with-overridden-fork-point",
                ),
            ),
            PositionalSpec(name="branch", required=False),
        ),
    ),
    CommandSpec(
        name="log",
        aliases=("l",),
        positionals=(PositionalSpec(name="branch", required=False),),
    ),
    CommandSpec(
        name="reapply",
        options=(OptSpec(short="f", long="fork-point", takes_value=True),),
    ),
    CommandSpec(
        name="rename",
        options=(
            OptSpec(short="b", long="branch", takes_value=True),
            OptSpec(long="repoint-tracking"),
        ),
        positionals=(PositionalSpec(name="new_name"),),
    ),
    CommandSpec(
        name="show",
        positionals=(
            PositionalSpec(
                name="direction",
                display_name="show direction",
                choices=_SHOW_DIRECTION_CHOICES,
            ),
            PositionalSpec(name="branch", required=False),
        ),
    ),
    CommandSpec(
        name="slide-out",
        options=(
            OptSpec(short="d", long="down-fork-point", takes_value=True),
            OptSpec(long="delete"),
            OptSpec(short="M", long="merge"),
            OptSpec(short="n"),
            OptSpec(long="no-edit-merge"),
            OptSpec(long="no-interactive-rebase"),
            OptSpec(long="no-rebase"),
            OptSpec(long="removed-from-remote"),
        ),
        mutex_groups=(
            MutexGroup(
                ("down-fork-point", "merge"),
                "Option `-d/--down-fork-point` only makes sense when using "
                "rebase and cannot be specified together with `-M/--merge`."),
            MutexGroup(
                ("down-fork-point", "no-rebase"),
                "Option `-d/--down-fork-point` only makes sense when using "
                "rebase and cannot be specified together with `--no-rebase`."),
            MutexGroup(
                ("merge", "no-rebase"),
                "Option `-M/--merge` cannot be specified together with `--no-rebase`."),
            MutexGroup(
                ("no-interactive-rebase", "no-rebase"),
                "Option `--no-interactive-rebase` only makes sense when using "
                "rebase and cannot be specified together with `--no-rebase`."),
            MutexGroup(
                ("no-edit-merge", "no-rebase"),
                "Option `--no-edit-merge` only makes sense when using "
                "merge and cannot be specified together with `--no-rebase`."),
            MutexGroup(
                ("no-interactive-rebase", "merge"),
                "Option `--no-interactive-rebase` only makes sense when using "
                "rebase and cannot be specified together with `-M/--merge`."),
        ),
        positionals=(PositionalSpec(name="branches", required=False, multiple=True),),
    ),
    CommandSpec(
        name="squash",
        options=(OptSpec(short="f", long="fork-point", takes_value=True),),
    ),
    CommandSpec(
        name="status",
        aliases=("s",),
        options=(
            OptSpec(long="color", takes_value=True),
            OptSpec(short="l", long="list-commits"),
            OptSpec(short="L", long="list-commits-with-hashes"),
            OptSpec(long="no-detect-squash-merges"),
            OptSpec(long="squash-merge-detection", takes_value=True),
        ),
    ),
    CommandSpec(
        name="traverse",
        aliases=("t",),
        options=(
            OptSpec(short="F", long="fetch"),
            OptSpec(short="H", long="sync-github-prs"),
            OptSpec(short="L", long="sync-gitlab-mrs"),
            OptSpec(short="l", long="list-commits"),
            OptSpec(short="M", long="merge"),
            OptSpec(short="n"),
            OptSpec(long="no-detect-squash-merges"),
            OptSpec(long="no-edit-merge"),
            OptSpec(long="no-interactive-rebase"),
            OptSpec(long="no-push"),
            OptSpec(long="no-push-untracked"),
            OptSpec(long="push"),
            OptSpec(long="push-untracked"),
            OptSpec(long="return-to", takes_value=True),
            OptSpec(long="squash-merge-detection", takes_value=True),
            OptSpec(long="start-from", takes_value=True),
            OptSpec(long="stop-after", takes_value=True),
            OptSpec(short="W"),
            OptSpec(short="w", long="whole"),
            OptSpec(short="y", long="yes"),
        ),
        mutex_groups=(
            MutexGroup(("sync-github-prs", "sync-gitlab-mrs")),
            MutexGroup(
                ("no-interactive-rebase", "merge"),
                "Option `--no-interactive-rebase` only makes sense when using "
                "rebase and cannot be specified together with `-M/--merge`."),
        ),
    ),
    CommandSpec(
        name="update",
        options=(
            OptSpec(short="f", long="fork-point", takes_value=True),
            OptSpec(short="M", long="merge"),
            OptSpec(short="n"),
            OptSpec(long="no-edit-merge"),
            OptSpec(long="no-interactive-rebase"),
        ),
        mutex_groups=(
            MutexGroup(
                ("no-interactive-rebase", "merge"),
                "Option `--no-interactive-rebase` only makes sense when using "
                "rebase and cannot be specified together with `-M/--merge`."),
            MutexGroup(
                ("fork-point", "merge"),
                "Option `-f/--fork-point` only makes sense when using rebase "
                "and cannot be specified together with `-M/--merge`."),
        ),
    ),
    CommandSpec(name="version"),
)


def _build_command_index() -> Dict[str, CommandSpec]:
    by_name: Dict[str, CommandSpec] = {}
    for spec in COMMANDS:
        by_name[spec.name] = spec
        for alias in spec.aliases:
            by_name[alias] = spec
    return by_name


COMMAND_BY_NAME_OR_ALIAS: Dict[str, CommandSpec] = _build_command_index()
