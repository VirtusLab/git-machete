"""Command-line parser for git-machete.

A small hand-rolled parser that lives on top of `getopt.gnu_getopt`. We did
use `argparse` here for years, but every interesting failure mode (typo
suggestions, scoped close-match hints, hidden-but-still-accepted choices,
required-positional listings, ...) ended up replaced by custom logic in
`CustomArgumentParser`, and the only thing argparse was still buying us
was the option-parsing primitive itself. Spelling that one out directly
turned out to be both shorter and easier to reason about than the
`argparse.ArgumentParser` + `_SubParsersAction` + `_check_value` machinery
we were overriding.

The module exposes:

* `OptSpec`, `PositionalSpec`, `MutexGroup`, `SubcommandSpec`, `CommandSpec`
  - declarative description of one (sub)command's command-line surface.
* `COMMANDS` / `COMMAND_BY_NAME_OR_ALIAS` - the actual table of git-machete
  commands.
* `parse_cmdline(argv) -> ParsedCmd` - the single entry point used by
  `cli.py`. Performs alias resolution, option parsing, choice + mutex +
  per-subcommand-option validation, and either returns a `ParsedCmd` or
  exits via `_argument_error()` (syntax errors) / `MacheteException`
  (semantic rejections like "this option is only valid with that
  subcommand").
"""

import difflib
import getopt
import itertools
import re
import sys
from typing import (Any, Callable, Dict, FrozenSet, Iterable, List, NamedTuple,
                    NoReturn, Optional, Tuple)

from git_machete.help import commands_and_aliases
from git_machete.utils import markup, terminal
from git_machete.utils.exceptions import ExitCode, MacheteException

_CLOSE_MATCH_CUTOFF = 0.6
_MAX_SUGGESTIONS = 3


# ────────────────────────────────────────────────────────────────────────────
# Spec types
# ────────────────────────────────────────────────────────────────────────────


class OptSpec(NamedTuple):
    """One option (long, short or both).

    `takes_value` is True iff the option requires an argument (e.g. `--onto
    foo` or `-o foo`). The display name used in error messages is built
    from whichever of `short`/`long` is set (preferring `-short/--long` if
    both are present, mirroring argparse).
    """
    long: Optional[str] = None
    short: Optional[str] = None
    takes_value: bool = False

    @property
    def canonical_name(self) -> str:
        """`-X/--long`, `--long`, or `-X` depending on what's defined."""
        if self.short and self.long:
            return f"-{self.short}/--{self.long}"
        if self.long:
            return f"--{self.long}"
        # Short-only options exist in COMMANDS (e.g. `-W`, `-n`) but none of
        # them currently participate in a mutex group, so the only
        # call site - the mutex-error formatter - never lands here.
        assert self.short is not None  # pragma: no cover
        return f"-{self.short}"  # pragma: no cover

    @property
    def storage_key(self) -> str:
        """Stable key used in the `opts` dict returned by the parser."""
        return self.long if self.long else (self.short or "")


class PositionalSpec(NamedTuple):
    """One positional argument.

    `multiple=True` collects every remaining positional into a list (the
    argparse `nargs='*'` case); `required=False` makes a single-valued
    positional optional (argparse's `nargs='?'`).

    `choices` constrains the allowed values; `hidden_choices` is the
    subset that's still accepted by the parser but never surfaced in
    error messages or close-match suggestions (used for the deprecated
    `github sync` subcommand).

    `display_name` overrides the human-readable label used in error
    messages while `name` stays the stable storage key (e.g. github's
    `request_id` storage key but `PR number` in errors).

    `only_with_subcommand`, when set, restricts this positional to a set
    of subcommands. Used together with the `subcommands` field of
    `CommandSpec` to surface "X is only valid with Y subcommand" errors
    from the parser rather than from the dispatcher.
    """
    name: str
    required: bool = True
    multiple: bool = False
    choices: Optional[Tuple[str, ...]] = None
    hidden_choices: FrozenSet[str] = frozenset()
    type_conv: Optional[Callable[[str], Any]] = None
    display_name: Optional[str] = None
    only_with_subcommand: Optional[Tuple[str, ...]] = None

    @property
    def label(self) -> str:
        return self.display_name or self.name


class MutexGroup(NamedTuple):
    """A set of options that may not be used together.

    `options` lists `OptSpec.storage_key`s. If two or more of them are
    set, the group fires.

    If `message` is None, the default argparse-style wording is emitted:
    `Argument X: not allowed with argument Y` (exit code
    `ARGUMENT_ERROR`). This is what argparse's
    `add_mutually_exclusive_group()` used to produce.

    If `message` is a string, it's raised verbatim as a
    `MacheteException` (exit code `MACHETE_EXCEPTION`). Use this for
    semantic rejections like "Option `-d/--down-fork-point` only makes
    sense when using rebase and cannot be specified together with
    `-M/--merge`." - the message is fully owned by the spec, doesn't
    depend on which option came first on the command line, and surfaces
    through the same `MacheteException` channel as the rest of the
    dispatcher's "Option X conflicts with Y" checks.
    """
    options: Tuple[str, ...]
    message: Optional[str] = None


class SubcommandSpec(NamedTuple):
    """One second-level subcommand of a command that dispatches on its
    first positional (currently `github` and `gitlab`).

    Each subcommand owns its own option set + mutex groups; the parser
    unions them across the command's subcommands for the actual parsing
    pass but validates that any option used on a given command line is
    accepted by the selected subcommand. `hidden=True` keeps the
    subcommand accepted by the parser while excluding it from
    user-facing listings (used for the deprecated `github sync`).
    """
    name: str
    options: Tuple[OptSpec, ...] = ()
    mutex_groups: Tuple[MutexGroup, ...] = ()
    hidden: bool = False


class CommandSpec(NamedTuple):
    """One git-machete command.

    `options`, `positionals` and `mutex_groups` describe what's accepted
    regardless of any subcommand. `subcommands`, when non-empty, makes
    the first positional a subcommand selector; the parser auto-generates
    its `PositionalSpec` (with the storage key `{cmd.name}_subcommand`
    and the display label `{cmd.name} subcommand`) and merges in the
    selected subcommand's options/mutex_groups for validation.
    """
    name: str
    aliases: Tuple[str, ...] = ()
    options: Tuple[OptSpec, ...] = ()
    positionals: Tuple[PositionalSpec, ...] = ()
    mutex_groups: Tuple[MutexGroup, ...] = ()
    subcommands: Tuple[SubcommandSpec, ...] = ()

    @property
    def subcommand_positional_name(self) -> str:
        return f"{self.name}_subcommand"

    @property
    def subcommand_display_label(self) -> str:
        return f"{self.name} subcommand"


class ParsedCmd(NamedTuple):
    """The output of `parse_cmdline`.

    `opts` keys are `OptSpec.storage_key` (the long name, or short if
    long-less). Boolean flags map to `""`; valued options map to their
    string value.

    `positionals` keys are `PositionalSpec.name` (the human-readable name
    used in error messages); the value is a string, list of strings, or
    list of converted values depending on `multiple`/`type_conv`.

    `pass_through` is everything after a literal `--` in argv.
    """
    command: Optional[str]  # canonical command name (alias resolved). None for "no command"
    opts: Dict[str, str]
    positionals: Dict[str, Any]
    pass_through: List[str]


# ────────────────────────────────────────────────────────────────────────────
# Common options (accepted before AND after the command, like argparse's
# `parents=[common_args_parser]` machinery used to do)
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


# ────────────────────────────────────────────────────────────────────────────
# Parsing
# ────────────────────────────────────────────────────────────────────────────


def parse_cmdline(argv: List[str]) -> ParsedCmd:
    """Parse `argv` into a `ParsedCmd` or exit with an argument error."""
    direct, pass_through = _split_on_dashdash(argv)

    # Locate the command in `direct`. Anything before it must be a
    # COMMON_OPTIONS flag; anything after is parsed against the merged
    # spec (common + command-specific + selected-subcommand).
    cmd_pos = _find_command_position(direct)

    if cmd_pos is None:
        # Either there are no positionals at all (`git machete --help`) or
        # the only "positional" we'd see is an unknown flag (e.g. `-q`).
        # Validate against COMMON_OPTIONS only and return.
        opts, _, unknowns = _scan(direct, COMMON_OPTIONS)
        _apply_color_setting(opts.get("color"))
        if unknowns:
            _fail_unrecognized(unknowns, command=None)
        return ParsedCmd(command=None, opts=opts, positionals={}, pass_through=pass_through)

    cmd_name_typed = direct[cmd_pos]
    cmd = COMMAND_BY_NAME_OR_ALIAS.get(cmd_name_typed)
    if cmd is None:
        _fail_invalid_command(cmd_name_typed)

    # Build the union of every option this command may accept on any
    # subcommand: needed so the option parser knows what's syntactically
    # valid. We later cross-check each used option against the SELECTED
    # subcommand and emit a friendlier "only valid with X subcommand"
    # error for the legal-but-not-here case.
    all_command_options = _collect_all_options(cmd)
    merged_options = COMMON_OPTIONS + all_command_options
    other_args = direct[:cmd_pos] + direct[cmd_pos + 1:]
    opts, positionals, unknowns = _scan(other_args, merged_options)
    # Apply `--color` before any downstream validation step that might
    # construct a `MacheteException`: the exception captures the current
    # `markup.use_ansi_escapes_in_*` values at __init__ time and rendering
    # is one-shot.
    _apply_color_setting(opts.get("color"))
    if unknowns:
        _fail_unrecognized(unknowns, command=cmd.name)

    # `--help` and `--version` are processed before positional/mutex
    # validation: argparse used to trigger their actions mid-parse, so
    # e.g. `git machete completion --help` printed the completion help
    # page without first complaining that the `shell` positional was
    # missing.
    if "help" in opts or "version" in opts:
        return ParsedCmd(command=cmd.name, opts=opts, positionals={}, pass_through=pass_through)

    effective_positionals = _effective_positionals(cmd)
    parsed_positionals = _validate_positionals(positionals, cmd, effective_positionals)

    selected_subcommand = _selected_subcommand(cmd, parsed_positionals)
    if cmd.subcommands and selected_subcommand is not None:
        _validate_subcommand_restrictions(opts, parsed_positionals, cmd, selected_subcommand)

    effective_mutex = cmd.mutex_groups + (
        selected_subcommand.mutex_groups if selected_subcommand is not None else ())
    _validate_mutex_groups(opts, effective_mutex, merged_options)

    return ParsedCmd(
        command=cmd.name,
        opts=opts,
        positionals=parsed_positionals,
        pass_through=pass_through,
    )


def _collect_all_options(cmd: CommandSpec) -> Tuple[OptSpec, ...]:
    seen: Dict[str, OptSpec] = {o.storage_key: o for o in cmd.options}
    for sub in cmd.subcommands:
        for o in sub.options:
            seen.setdefault(o.storage_key, o)
    return tuple(seen.values())


def _effective_positionals(cmd: CommandSpec) -> Tuple[PositionalSpec, ...]:
    """Build the final positional list for this command, prepending a
    synthetic subcommand selector when `cmd.subcommands` is non-empty."""
    if not cmd.subcommands:
        return cmd.positionals
    selector = PositionalSpec(
        name=cmd.subcommand_positional_name,
        display_name=cmd.subcommand_display_label,
        choices=tuple(s.name for s in cmd.subcommands),
        hidden_choices=frozenset(s.name for s in cmd.subcommands if s.hidden),
    )
    return (selector,) + cmd.positionals


def _selected_subcommand(
        cmd: CommandSpec,
        parsed_positionals: Dict[str, Any],
) -> Optional[SubcommandSpec]:
    if not cmd.subcommands:
        return None
    name = parsed_positionals.get(cmd.subcommand_positional_name)
    if name is None:  # pragma: no cover
        # Unreachable in practice: `_validate_positionals` rejects a missing
        # required subcommand positional before this function is called.
        return None
    return next((s for s in cmd.subcommands if s.name == name), None)


# --- Internal helpers ------------------------------------------------------


def _split_on_dashdash(argv: List[str]) -> Tuple[List[str], List[str]]:
    direct = list(itertools.takewhile(lambda a: a != "--", argv))
    after = list(itertools.dropwhile(lambda a: a != "--", argv))
    pass_through = after[1:] if after else []
    return direct, pass_through


def _find_command_position(direct: List[str]) -> Optional[int]:
    """Walk `direct`, skipping COMMON_OPTIONS flags, and return the index of
    the first positional token. `None` if there is no positional at all
    (or if we hit something option-looking we can't classify - in which
    case the parser will surface it as an unknown flag below)."""
    common_long = {o.long for o in COMMON_OPTIONS if o.long}
    common_short = {o.short for o in COMMON_OPTIONS if o.short}
    i = 0
    while i < len(direct):
        a = direct[i]
        if a.startswith("--"):
            name = a[2:].split("=", 1)[0]
            if name in common_long:
                # None of COMMON_OPTIONS take a value, so just step over.
                i += 1
                continue
            # Unknown long option in the top-level segment - bail out
            # without picking a command. The unknown-flag scan downstream
            # will turn this into a proper error.
            return None
        if a.startswith("-") and len(a) > 1:
            short = a[1:]
            # Single-letter short → check against COMMON_OPTIONS; longer
            # `-XXX` (e.g. `-gs`) is by definition not a COMMON_OPTIONS
            # short flag, so bail out for the same reason as above.
            if len(short) == 1 and short in common_short:
                i += 1
                continue
            return None
        return i
    return None


def _scan(
        argv: List[str],
        options: Iterable[OptSpec],
) -> Tuple[Dict[str, str], List[str], List[str]]:
    """The actual option scanner.

    Uses `getopt.gnu_getopt` for the happy path (so we inherit its handling
    of `--long=value`, `--long value`, `-x value`, `-xvalue`, combined
    short flags, ...). On `GetoptError` we fall back to a single-pass
    manual sweep that collects EVERY unknown flag (and its trailing value,
    if any) so the user sees them all at once - rather than getting picked
    off one by one as they fix typos.

    Returns `(opts, positionals, unknown_flag_tokens)`. `unknown_flag_tokens`
    is the raw arg list as the user typed it (e.g. `["--srart-from", "foo"]`)
    so the error formatter can re-emit it verbatim.
    """
    long_specs: Dict[str, OptSpec] = {o.long: o for o in options if o.long}
    short_specs: Dict[str, OptSpec] = {o.short: o for o in options if o.short}

    # Build getopt-format short/long strings.
    short_str = "".join(
        s + (":" if spec.takes_value else "")
        for s, spec in short_specs.items()
    )
    long_list = [
        (lng + "=" if spec.takes_value else lng)
        for lng, spec in long_specs.items()
    ]

    # `getopt` treats `-b=foo` as `-b` with value `"=foo"`, but argparse
    # (and historical git-machete) treat it as `-b foo`. Normalize the
    # `-X=value` form so callers can use either syntax.
    normalized_argv = []
    for a in argv:
        if (len(a) >= 4 and a.startswith("-") and not a.startswith("--") and
                a[1] in short_specs and short_specs[a[1]].takes_value and
                a[2] == "="):
            normalized_argv.append(a[:2])
            normalized_argv.append(a[3:])
        else:
            normalized_argv.append(a)

    try:
        pairs, positionals = getopt.gnu_getopt(normalized_argv, short_str, long_list)
    except getopt.GetoptError as e:
        # Recover all unknowns ourselves, so the error message lists every
        # bad token at once.
        unknown_tokens = _collect_unknown_tokens(argv, long_specs, short_specs)
        if unknown_tokens:
            return {}, [], unknown_tokens
        # getopt raised for some other reason (typically "option X requires
        # argument" when the user passes a value-taking flag with no value
        # after it). Surface as a regular argument error rather than an
        # uncaught GetoptError.
        _argument_error(_humanize_getopt_error(e, long_specs, short_specs))

    opts: Dict[str, str] = {}
    for raw_flag, raw_value in pairs:
        spec = (long_specs[raw_flag[2:]] if raw_flag.startswith("--")
                else short_specs[raw_flag[1:]])
        opts[spec.storage_key] = raw_value if spec.takes_value else ""
    return opts, positionals, []


def _humanize_getopt_error(
        err: getopt.GetoptError,
        long_specs: Dict[str, OptSpec],
        short_specs: Dict[str, OptSpec],
) -> str:
    """Re-cast getopt's lowercase, hard-coded "option X requires argument"
    style message into the argparse-flavoured "Argument -X/--long:
    expected one argument" wording the rest of the parser uses."""
    opt = err.opt
    # `err.opt` carries the short letter or long name WITHOUT the leading
    # dashes; promote it back to whichever canonical form we recognise.
    spec = (long_specs.get(opt) if len(opt) > 1 else None) or short_specs.get(opt)
    label = spec.canonical_name if spec else (f"--{opt}" if len(opt) > 1 else f"-{opt}")
    # getopt's own messages are stable but lowercase; sentence-cap them to
    # match the rest of the parser's diagnostics. Strip the leading
    # `option --X ` / `option -X ` prefix since we already lead with
    # `Argument {label}:`.
    if "requires argument" in str(err):
        return f"Argument {label}: expected one argument"
    tail = re.sub(r"^option -{1,2}\S+\s+", "", err.msg)
    return f"Argument {label}: {tail}"


def _collect_unknown_tokens(
        argv: List[str],
        long_specs: Dict[str, OptSpec],
        short_specs: Dict[str, OptSpec],
) -> List[str]:
    """Walk `argv` once and return the user-typed tokens of every unknown
    flag, paired with their adjacent value when one was supplied.

    The output is meant to be re-emitted verbatim in the error message,
    so we preserve the user's syntax (e.g. `--foo=bar` stays a single
    token while `--foo bar` stays two).
    """
    unknown: List[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            name = a[2:].split("=", 1)[0]
            if name in long_specs:
                spec = long_specs[name]
                if spec.takes_value and "=" not in a and i + 1 < len(argv):
                    i += 1  # consume the value
            else:
                unknown.append(a)
                # If `--foo bar` (no `=`) and `bar` is unlikely to be its
                # own flag, also include it for display so the user sees
                # the full unrecognised pair.
                if "=" not in a and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                    i += 1
                    unknown.append(argv[i])
            i += 1
            continue
        if a.startswith("-") and len(a) > 1:
            short = a[1:]
            # Match `-X`, `-Xvalue` (when -X takes a value) but treat
            # anything else (e.g. `-gs`, `-q`) as unknown.
            if short[0] in short_specs and (
                    len(short) == 1 or short_specs[short[0]].takes_value):
                spec = short_specs[short[0]]
                if spec.takes_value and len(short) == 1 and i + 1 < len(argv):
                    i += 1
            else:
                unknown.append(a)
            i += 1
            continue
        i += 1
    return unknown


# ────────────────────────────────────────────────────────────────────────────
# Validation + error formatting
# ────────────────────────────────────────────────────────────────────────────


def _close_matches(value: str, candidates: Iterable[str]) -> List[str]:
    return difflib.get_close_matches(
        value, list(candidates), n=_MAX_SUGGESTIONS, cutoff=_CLOSE_MATCH_CUTOFF)


def _format_suggestions(suggestions: List[str], *, capitalize: bool = True) -> str:
    quoted = ", ".join(f"`{s}`" for s in suggestions)
    lead = "Did" if capitalize else "did"
    return f"{lead} you mean: {quoted}?"


def _format_choices(choices: Iterable[str]) -> str:
    return ", ".join(str(c) for c in choices)


def _visible_choices(positional: PositionalSpec) -> Tuple[str, ...]:
    # Callers (`_fail_invalid_choice`, `_fail_missing_required`) only
    # reach this helper for positionals that already carry `choices=`, so
    # the empty-choices fallback is just a safety net.
    if not positional.choices:  # pragma: no cover
        return ()
    return tuple(c for c in positional.choices if c not in positional.hidden_choices)


def _apply_color_setting(color: Optional[str]) -> None:
    """Honour `--color` for stdout / stderr ANSI emission.

    Called from inside `parse_cmdline` (rather than waiting until the
    caller invokes `set_utils_global_variables`) so that any
    `MacheteException` raised from the validation phase below picks up
    the same flag values that the rest of the program will use. The
    exception's `.msg` is rendered once at `__init__` time, so the
    globals must be correct BEFORE the raise.
    """
    use_in_stdout = color == "always" or (color in {None, "auto"} and terminal.is_stdout_a_tty())
    use_in_stderr = color == "always" or (color in {None, "auto"} and terminal.is_stderr_a_tty())
    markup.use_ansi_escapes_in_stdout = use_in_stdout
    markup.use_ansi_escapes_in_stderr = use_in_stderr


def _argument_error(message: str) -> NoReturn:
    sys.stderr.write(message + "\n")
    sys.exit(ExitCode.ARGUMENT_ERROR)


def _fail_invalid_command(typed: str) -> NoReturn:
    lines = [f"Invalid command: {typed!r}"]
    # Build the user-visible vocabulary from canonical names + aliases.
    visible = [n for n, spec in COMMAND_BY_NAME_OR_ALIAS.items() if n == spec.name or n in spec.aliases]
    suggestions = _close_matches(typed, visible)
    if suggestions:
        lines.append(_format_suggestions(suggestions))
    else:
        # With ~30 commands the full listing would dwarf the error, so
        # steer the user to `help` instead - same trade-off as argparse-era.
        lines.append("Run `git machete help` to see all available commands.")
    _argument_error("\n".join(lines))


def _fail_unrecognized(unknown_tokens: List[str], *, command: Optional[str]) -> NoReturn:
    message = "Unrecognized arguments: " + " ".join(unknown_tokens)

    # Build per-flag suggestions. `--foo=bar` is split before fuzzy-matching
    # so `--foo` (the actual misspelling) is what we compare against.
    flag_suggestions: List[Tuple[str, List[str]]] = []
    known_options = COMMON_OPTIONS + (
        COMMAND_BY_NAME_OR_ALIAS[command].options if command is not None else ()
    )
    known_flags = [f"--{o.long}" for o in known_options if o.long]
    for tok in unknown_tokens:
        if not tok.startswith("-"):
            continue
        flag = tok.split("=", 1)[0]
        close = _close_matches(flag, known_flags)
        if close:
            flag_suggestions.append((flag, close))

    if len(flag_suggestions) == 1:
        message += "\n" + _format_suggestions(flag_suggestions[0][1])
    elif flag_suggestions:
        lines = [
            f"For `{flag}`: {_format_suggestions(close, capitalize=False)}"
            for flag, close in flag_suggestions
        ]
        message += "\n" + "\n".join(lines)
    elif command is not None:
        message += f"\nSee `git machete help {command}` for usage."
    _argument_error(message)


def _validate_positionals(
        positionals: List[str],
        cmd: CommandSpec,
        positional_specs: Tuple[PositionalSpec, ...],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    remaining = list(positionals)

    for idx, pspec in enumerate(positional_specs):
        is_last = idx == len(positional_specs) - 1
        if pspec.multiple:
            # Consumes the rest of the positionals.
            values = remaining
            remaining = []
            if pspec.required and not values:  # pragma: no cover
                # No `multiple=True, required=True` positional currently
                # exists in COMMANDS - kept as a safety net so we'd notice
                # immediately if a future command introduced one without
                # also adding a test.
                _fail_missing_required(pspec)
            converted = [_convert_positional(pspec, v) for v in values]
            result[pspec.name] = converted
        else:
            if not remaining:
                if pspec.required:
                    _fail_missing_required(pspec)
                continue
            value = remaining.pop(0)
            if pspec.choices is not None and value not in pspec.choices:
                _fail_invalid_choice(pspec, value)
            result[pspec.name] = _convert_positional(pspec, value)
        if is_last and remaining:
            # Excess positionals → reported as unrecognized arguments,
            # matching argparse-era behaviour.
            _fail_unrecognized(remaining, command=cmd.name)

    if remaining:
        # The command declares no positionals but the user passed some.
        _fail_unrecognized(remaining, command=cmd.name)

    return result


def _convert_positional(pspec: PositionalSpec, value: str) -> Any:
    if pspec.type_conv is None:
        return value
    try:
        return pspec.type_conv(value)
    except ValueError:
        # Match argparse's wording closely enough that no current test breaks;
        # there is no test pinning this exact phrasing today.
        type_name = getattr(pspec.type_conv, "__name__", "value")
        _argument_error(f"Argument {pspec.label}: invalid {type_name} value: {value!r}")


def _fail_invalid_choice(pspec: PositionalSpec, value: str) -> NoReturn:
    visible = _visible_choices(pspec)
    lines = [f"Invalid {pspec.label}: {value!r}"]
    suggestions = _close_matches(value, visible)
    if suggestions:
        lines.append(_format_suggestions(suggestions))
    else:
        lines.append(f"Possible values for {pspec.label} are: " + _format_choices(visible))
    _argument_error("\n".join(lines))


def _fail_missing_required(pspec: PositionalSpec) -> NoReturn:
    lines = [f"The following arguments are required: {pspec.label}"]
    if pspec.choices:
        lines.append(
            f"Possible values for {pspec.label} are: " +
            _format_choices(_visible_choices(pspec))
        )
    _argument_error("\n".join(lines))


def _validate_mutex_groups(
        opts: Dict[str, str],
        groups: Tuple[MutexGroup, ...],
        all_options: Tuple[OptSpec, ...],
) -> None:
    option_by_key = {o.storage_key: o for o in all_options}
    for group in groups:
        seen: List[str] = [key for key in group.options if key in opts]
        if len(seen) < 2:
            continue
        if group.message is not None:
            # Semantic rejection - propagated as MacheteException so it
            # shows up via `assert_failure` and exits with
            # MACHETE_EXCEPTION just like the dispatcher's own
            # "Option X conflicts with Y" errors used to.
            raise MacheteException(group.message)
        first = option_by_key[seen[0]].canonical_name
        second = option_by_key[seen[1]].canonical_name
        _argument_error(f"Argument {second}: not allowed with argument {first}")


def _validate_subcommand_restrictions(
        opts: Dict[str, str],
        parsed_positionals: Dict[str, Any],
        cmd: CommandSpec,
        selected: SubcommandSpec,
) -> None:
    """For every option/positional that's been parsed, verify the selected
    subcommand accepts it. Raise `MacheteException` with the historical
    `<thing> is only valid with <sub> subcommand(s).` wording if not."""

    # ---- options ----------------------------------------------------------
    selected_keys = {o.storage_key for o in selected.options}
    common_keys = {o.storage_key for o in cmd.options} | {o.storage_key for o in COMMON_OPTIONS}
    for key in opts:
        if key in selected_keys or key in common_keys:
            continue
        offering = [s.name for s in cmd.subcommands
                    if any(o.storage_key == key for o in s.options)]
        if not offering:
            # Should be unreachable: the parser only accepts options that
            # belong to SOMETHING.
            continue  # pragma: no cover
        opt_spec = _find_option_by_key(cmd, key)
        flag_label = f"--{opt_spec.long}" if opt_spec and opt_spec.long else f"-{key}"
        raise MacheteException(
            f"`{flag_label}` option is only valid with "
            f"{_format_subcommand_list(offering)} {_subcommand_word(offering)}."
        )

    # ---- positionals ------------------------------------------------------
    for pspec in cmd.positionals:
        if pspec.only_with_subcommand is None:  # pragma: no cover
            # Every positional declared on a command-with-subcommands
            # currently scopes itself to a subcommand (github/gitlab's
            # `request_id`); the unrestricted branch is kept defensively.
            continue
        value = parsed_positionals.get(pspec.name)
        # `multiple` positionals come back as lists; treat empty/None as
        # "not supplied" so we only fire when the user actually provided
        # the positional under the wrong subcommand.
        if not value:
            continue
        if selected.name in pspec.only_with_subcommand:
            continue
        subs = list(pspec.only_with_subcommand)
        raise MacheteException(
            f"{pspec.label} is only valid with "
            f"{_format_subcommand_list(subs)} {_subcommand_word(subs)}."
        )


def _find_option_by_key(cmd: CommandSpec, key: str) -> Optional[OptSpec]:
    # Flatten cmd-level options and per-subcommand options into one stream so
    # we don't need a separately-tested branch for each level - in practice
    # the only caller is the github/gitlab subcommand-restriction validator,
    # which only ever queries keys defined on a subcommand (cmd.options is
    # empty for both code-hosting commands).
    candidates = itertools.chain(
        cmd.options,
        *(sub.options for sub in cmd.subcommands),
    )
    return next((o for o in candidates if o.storage_key == key), None)


def _format_subcommand_list(names: List[str]) -> str:
    quoted = [f"`{n}`" for n in names]
    if len(quoted) == 1:
        return quoted[0]
    if len(quoted) == 2:
        return f"{quoted[0]} and {quoted[1]}"
    return ", ".join(quoted[:-1]) + f" and {quoted[-1]}"


def _subcommand_word(names: List[str]) -> str:
    return "subcommand" if len(names) == 1 else "subcommands"
