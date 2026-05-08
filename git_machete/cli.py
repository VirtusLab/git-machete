#!/usr/bin/env python3

import argparse
import difflib
import itertools
import os
import pkgutil
import sys
from typing import (Any, Dict, FrozenSet, Iterable, Iterator, List, NoReturn,
                    Optional, Sequence, Set, Tuple, TypeVar)

import git_machete.options
from git_machete import __version__
from git_machete.client.advance import AdvanceMacheteClient
from git_machete.client.anno import AnnoMacheteClient
from git_machete.client.base import MacheteClient
from git_machete.client.diff import DiffMacheteClient
from git_machete.client.discover import DiscoverMacheteClient
from git_machete.client.fork_point import ForkPointMacheteClient
from git_machete.client.go_interactive import GoInteractiveMacheteClient
from git_machete.client.go_show import GoShowMacheteClient
from git_machete.client.list import ListMacheteClient
from git_machete.client.log import LogMacheteClient
from git_machete.client.reapply import ReapplyMacheteClient
from git_machete.client.rename import RenameMacheteClient
from git_machete.client.slide_out import SlideOutMacheteClient
from git_machete.client.squash import SquashMacheteClient
from git_machete.client.status import StatusMacheteClient
from git_machete.client.traverse import (TraverseMacheteClient,
                                         TraverseReturnTo, TraverseStartFrom)
from git_machete.client.update import UpdateMacheteClient
from git_machete.client.with_code_hosting import MacheteClientWithCodeHosting
from git_machete.config import MacheteConfig, SquashMergeDetection
from git_machete.github import GITHUB_API_SPEC
from git_machete.gitlab import GITLAB_API_SPEC

from .git import AnyRevision, Git, LocalBranchShortName
from .help import (MacheteHelpAction, alias_by_command, commands_and_aliases,
                   get_help_description, version)
from .utils import cmd, debug_log, markup, terminal
from .utils.exceptions import (ExitCode, InteractionStopped, MacheteException,
                               UnderlyingGitException,
                               UnexpectedMacheteException)
from .utils.fs import does_directory_exist, get_current_directory_or_none
from .utils.markup import green_ok, print_fmt, warn
from .utils.paths import abspath_posix, join_paths_posix

T = TypeVar('T')


_CLOSE_MATCH_CUTOFF = 0.6
_MAX_SUGGESTIONS = 3


def _format_choices(choices: Iterable[Any]) -> str:
    return ", ".join(str(c) for c in choices)


def _close_matches(value: str, candidates: Iterable[str]) -> List[str]:
    return difflib.get_close_matches(
        value, list(candidates), n=_MAX_SUGGESTIONS, cutoff=_CLOSE_MATCH_CUTOFF)


def _format_suggestions(suggestions: List[str], *, capitalize: bool = True) -> str:
    quoted = ", ".join(f"`{s}`" for s in suggestions)
    lead = "Did" if capitalize else "did"
    return f"{lead} you mean: {quoted}?"


def _visible_choices(action: argparse.Action) -> List[str]:
    """`action.choices` minus any `_hidden_from_listing` entries (deprecated
    aliases / undocumented escape hatches that we don't want to surface in
    user-facing hints or fuzzy-match suggestions, even though they remain
    accepted by the parser).
    """
    hidden: FrozenSet[str] = getattr(action, "_hidden_from_listing", frozenset())
    # `_visible_choices` is only ever called on actions where `action.choices`
    # is non-None (gated by the call sites), so the cast is safe.
    return [str(c) for c in (action.choices or ()) if c not in hidden]


def _displayed_action_name(action: argparse.Action) -> str:
    """Mirrors argparse's `_get_action_name` precedence (option strings -> metavar -> dest)."""
    # The option-strings branch only fires for required `--flag`s and we have none
    # today (the only required actions in our parser are subparser-selector
    # positionals). Kept for parity with `argparse._get_action_name` so that future
    # additions of required flags get a sensible label automatically.
    if action.option_strings:  # pragma: no cover
        return "/".join(action.option_strings)
    if action.metavar not in (None, argparse.SUPPRESS):
        # `metavar` is typed as `Optional[str]` but at this point it cannot be None or SUPPRESS.
        return str(action.metavar)
    return action.dest


class CustomArgumentParser(argparse.ArgumentParser):
    """An ArgumentParser with friendlier - and fully owned - error messages.

    The standard argparse failure modes (invalid choice, missing required
    positional, unknown option) are too terse and offer no fix when the user
    makes a typo. Worse, the only public extension point - `error()` - sees
    pre-formatted English strings, which forces any enrichment to pattern-match
    on argparse's wording and breaks under translations or future Python
    versions.

    To avoid that coupling, this parser:

    * overrides `_check_value` so invalid-choice errors are emitted with our
      own message (capitalized prefix, no `(choose from ...)` litany) and
      enriched with `difflib.get_close_matches` hints,
    * overrides `parse_args` to disable argparse's built-in "missing required"
      check (by clearing `action.required` across the parser tree before
      delegating to `parse_known_args`), then re-validates afterwards using
      direct introspection of the `Action` objects - no string parsing of
      argparse output,
    * scopes "unrecognized argument" suggestions to the active subparser, so
      the proposed alternatives are options the dispatched (sub)command will
      actually accept,
    * skips argparse's auto-generated `usage:` / `prog: error:` boilerplate,
      since `MacheteHelpAction` is the canonical place for usage output.
    """

    def _check_value(self, action: argparse.Action, value: Any) -> None:
        # Argparse would normally raise `ArgumentError(action, msg)` here, which
        # gets stringified as `argument <name>: invalid choice: <value> (choose
        # from <list>)`. We bypass that and call `self.error` with a fully owned
        # message instead - shorter, more natural-sounding and not weighed down
        # by a possibly very long `(choose from ...)` listing.
        if action.choices is not None and value not in action.choices:
            visible = _visible_choices(action)
            lines = [f"Invalid {_displayed_action_name(action)}: {value!r}"]
            suggestions = _close_matches(str(value), visible)
            if suggestions:
                lines.append(_format_suggestions(suggestions))
            elif action.dest == "command" and self.prog == "git machete":
                # Top-level command typo without a near-miss: with ~30 commands
                # the full listing would dwarf the error, so just steer the user
                # to `help` instead.
                lines.append("Run `git machete help` to see all available commands.")
            else:
                # Nested choice (github/gitlab subcommand, go/show direction,
                # `--color` value, ...) with no near-miss: the set is small
                # enough that printing it all is more helpful than asking the
                # user to dig further.
                lines.append(f"Possible values for {_displayed_action_name(action)} are: " + _format_choices(visible))
            self.error("\n".join(lines))

    def parse_args(  # type: ignore[override]
            self,
            args: Optional[Sequence[str]] = None,
            namespace: Optional[argparse.Namespace] = None,
    ) -> argparse.Namespace:
        # Temporarily clear `required` on every action in the parser tree so
        # that `parse_known_args` never reaches the path where argparse builds
        # its English `the following arguments are required: ...` message
        # (whose wording and capitalization we don't control).
        # We restore the flags afterwards and re-validate with full ownership
        # of the resulting message (including the choices listing).
        was_required = [a for a in self._iter_actions_recursive() if a.required]
        for action in was_required:
            action.required = False
        try:
            parsed, leftovers = self.parse_known_args(args, namespace)
        finally:
            for action in was_required:
                action.required = True

        if leftovers:
            self._fail_for_unrecognized(leftovers, parsed)

        missing = self._find_missing_required(parsed, was_required)
        if missing:
            self._fail_for_missing_required(missing)

        return parsed

    def error(self, message: str) -> NoReturn:
        # Reached for the failure modes argparse handles itself (invalid type,
        # invalid value via `_check_value` -> `ArgumentError`, ambiguous option,
        # etc.) as well as for our own custom messages. We always print bare;
        # `MacheteHelpAction` is the canonical place for usage output.
        sys.stderr.write(message + "\n")
        self.exit(ExitCode.ARGUMENT_ERROR)

    def _iter_actions_recursive(self) -> Iterator[argparse.Action]:
        seen_parsers: Set[int] = set()
        stack: List[argparse.ArgumentParser] = [self]
        while stack:
            parser = stack.pop()
            if id(parser) in seen_parsers:
                continue
            seen_parsers.add(id(parser))
            for action in parser._actions:
                yield action
                if isinstance(action, argparse._SubParsersAction):
                    stack.extend(action.choices.values())

    def _active_parser_chain(self, parsed: argparse.Namespace) -> List[argparse.ArgumentParser]:
        """Return the chain of (sub)parsers actually invoked, root-first."""
        chain: List[argparse.ArgumentParser] = [self]
        parser: argparse.ArgumentParser = self
        while True:
            sub_action = next(
                (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
                None)
            if sub_action is None:
                break
            sub_value = getattr(parsed, sub_action.dest, None)
            if sub_value is None or sub_value not in sub_action.choices:
                break
            parser = sub_action.choices[sub_value]
            chain.append(parser)
        return chain

    def _find_missing_required(
            self,
            parsed: argparse.Namespace,
            candidates: List[argparse.Action],
    ) -> List[argparse.Action]:
        """Return the originally-required actions belonging to an active parser
        whose value didn't actually land in the namespace.

        Note: `argparse._get_positional_kwargs` on Python < 3.12 sets
        `required=True` on `nargs='*'` positionals whenever the parser uses
        `argument_default=argparse.SUPPRESS`, even though such positionals
        legitimately accept zero values - see CPython gh-95292. We therefore
        also filter on `nargs` here so a `nargs='*'` action that consumed
        zero values is never reported as missing, regardless of what argparse
        internally flagged as required.
        """
        active = {id(p) for p in self._active_parser_chain(parsed)}
        owners = self._build_action_owner_map()
        parsed_keys = vars(parsed)
        missing: List[argparse.Action] = []
        for action in candidates:
            owner = owners.get(id(action))
            if owner is None or id(owner) not in active:
                continue
            if action.nargs in ("?", "*", argparse.REMAINDER, argparse.SUPPRESS):
                continue
            if action.dest not in parsed_keys:
                missing.append(action)
        return missing

    def _build_action_owner_map(self) -> Dict[int, argparse.ArgumentParser]:
        owners: Dict[int, argparse.ArgumentParser] = {}
        seen_parsers: Set[int] = set()
        stack: List[argparse.ArgumentParser] = [self]
        while stack:
            parser = stack.pop()
            if id(parser) in seen_parsers:
                continue
            seen_parsers.add(id(parser))
            for action in parser._actions:
                owners.setdefault(id(action), parser)
                if isinstance(action, argparse._SubParsersAction):
                    stack.extend(action.choices.values())
        return owners

    def _fail_for_unrecognized(
            self,
            leftovers: List[str],
            parsed: argparse.Namespace,
    ) -> NoReturn:
        chain = self._active_parser_chain(parsed)
        active_parser = chain[-1]
        known_options = [
            opt for action in active_parser._actions
            for opt in action.option_strings
        ]

        # Collect (flag, close_matches) for every unrecognized option-like arg.
        flag_suggestions: List[Tuple[str, List[str]]] = []
        for arg in leftovers:
            if not arg.startswith("-"):
                continue
            # `--flag=value` -> match against `--flag` only
            flag = arg.split("=", 1)[0]
            close = _close_matches(flag, known_options)
            if close:
                flag_suggestions.append((flag, close))

        message = "Unrecognized arguments: " + " ".join(leftovers)
        if len(flag_suggestions) == 1:
            # Single suggestion: the flag already appears on the "Unrecognized
            # arguments" line so the "For `flag`:" prefix would be redundant.
            _, close = flag_suggestions[0]
            message += "\n" + _format_suggestions(close)
        elif flag_suggestions:
            # Multiple flags with suggestions: prefix each line so the user can
            # tell which suggestion belongs to which argument.
            lines = [f"For `{flag}`: {_format_suggestions(close, capitalize=False)}"
                     for flag, close in flag_suggestions]
            message += "\n" + "\n".join(lines)
        elif len(chain) > 1:
            # No spelling-correction hint available: point to the subcommand's
            # help page.  chain[1] is always the top-level subcommand parser.
            top_cmd = chain[1].prog.split()[-1]
            message += f"\nSee `git machete help {top_cmd}` for usage."
        self.error(message)

    def _fail_for_missing_required(self, actions: List[argparse.Action]) -> NoReturn:
        names = [_displayed_action_name(a) for a in actions]
        lines = ["The following arguments are required: " + ", ".join(names)]
        for action in actions:
            # All required actions in our parser today are subparser selectors and so
            # always have `choices`; the falsy branch is kept defensively for any
            # future required positional (e.g. a filename) that wouldn't have any.
            if action.choices:  # pragma: no branch
                choices_str = _format_choices(_visible_choices(action))
                lines.append(f"Possible values for {_displayed_action_name(action)} are: {choices_str}")
        self.error("\n".join(lines))


def create_cli_parser() -> argparse.ArgumentParser:
    common_args_parser = argparse.ArgumentParser(
        prog='git machete',
        argument_default=argparse.SUPPRESS,
        add_help=False)
    common_args_parser.add_argument('--debug', action='store_true')
    common_args_parser.add_argument('-h', '--help', action=MacheteHelpAction)
    common_args_parser.add_argument('--version', action='version', version=f'git-machete version {__version__}')
    common_args_parser.add_argument('-v', '--verbose', action='store_true')

    cli_parser: argparse.ArgumentParser = CustomArgumentParser(
        prog='git machete',
        argument_default=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])

    subparsers = cli_parser.add_subparsers(dest='command')

    def create_subparser(command: str, alias: Optional[str] = None) -> argparse.ArgumentParser:
        return subparsers.add_parser(
            command,
            aliases=[alias] if alias else [],
            argument_default=argparse.SUPPRESS,
            usage=argparse.SUPPRESS,
            add_help=False,
            parents=[common_args_parser])

    add_parser = create_subparser('add')
    add_parser.add_argument('branch', nargs='?')
    add_parser.add_argument('-f', '--as-first-child', action='store_true')
    add_parser.add_argument('-o', '--onto')
    add_parser.add_argument('-R', '--as-root', action='store_true')
    add_parser.add_argument('-y', '--yes', action='store_true')

    advance_parser = create_subparser('advance')
    advance_parser.add_argument('-y', '--yes', action='store_true')

    anno_parser = create_subparser('anno')
    # possible values of 'annotation_text' include: [], [''], ['some_val'], ['text_1', 'text_2']
    anno_parser.add_argument('annotation_text', nargs='*')
    anno_parser.add_argument('-b', '--branch')
    anno_parser.add_argument('-H', '--sync-github-prs', action='store_true')
    anno_parser.add_argument('-L', '--sync-gitlab-mrs', action='store_true')

    clean_parser = create_subparser('clean')
    clean_parser.add_argument('-H', '--checkout-my-github-prs', action='store_true')
    clean_parser.add_argument('-y', '--yes', action='store_true')

    completion_parser = create_subparser('completion')
    completion_parser.add_argument('shell', choices=['bash', 'fish', 'zsh'])

    delete_unmanaged_parser = create_subparser('delete-unmanaged')
    delete_unmanaged_parser.add_argument('-y', '--yes', action='store_true')

    diff_full_parser = create_subparser('diff', alias='d')
    diff_full_parser.add_argument('branch', nargs='?')
    diff_full_parser.add_argument('-s', '--stat', action='store_true')

    discover_parser = create_subparser('discover')
    discover_parser.add_argument('-C', '--checked-out-since')
    discover_parser.add_argument('-l', '--list-commits', action='store_true')
    discover_parser.add_argument('-r', '--roots')
    discover_parser.add_argument('-y', '--yes', action='store_true')

    create_subparser('edit', alias='e')

    create_subparser('file')

    fork_point_parser = create_subparser('fork-point')
    fork_point_parser.add_argument('branch', nargs='?')
    fork_point_parser.add_argument('--explain', action='store_true')
    fork_point_exclusive_optional_args = fork_point_parser.add_mutually_exclusive_group()
    fork_point_exclusive_optional_args.add_argument('--inferred', action='store_true')
    fork_point_exclusive_optional_args.add_argument('--override-to')
    fork_point_exclusive_optional_args.add_argument('--override-to-inferred', action='store_true')
    fork_point_exclusive_optional_args.add_argument('--override-to-parent', action='store_true')
    fork_point_exclusive_optional_args.add_argument('--unset-override', action='store_true')

    def add_code_hosting_parser(command: str, pr_or_mr: str, include_sync: bool) -> Any:
        parser = create_subparser(command)
        subcommand_action = parser.add_argument(
            'subcommand', metavar=f'{command} subcommand', choices=[
                f'anno-{pr_or_mr}s',
                f'checkout-{pr_or_mr}s',
                f'create-{pr_or_mr}',
                f'restack-{pr_or_mr}',
                f'retarget-{pr_or_mr}',
                f'update-{pr_or_mr}-descriptions'
            ] + (['sync'] if include_sync else []))
        if include_sync:
            # `github sync` is deep into deprecation - keep it accepted for now,
            # but never surface it in user-facing listings or close-match
            # suggestions. See `_visible_choices` for how this is honored.
            setattr(subcommand_action, '_hidden_from_listing', frozenset({'sync'}))
        parser.add_argument('request_id', nargs='*', type=int)
        parser.add_argument('-b', '--branch')
        parser.add_argument('--all', action='store_true')
        # Intentionally undocumented (see commit 336c152): an escape hatch for the rare
        # case when the parent branch detected by git-machete isn't the desired PR/MR
        # base. Not exposed in --help, RST docs, manpage or shell completions on purpose.
        parser.add_argument('--base')
        parser.add_argument('--by')
        parser.add_argument('--draft', action='store_true')
        parser.add_argument('--ignore-if-missing', action='store_true')
        parser.add_argument('--mine', action='store_true')
        parser.add_argument('--related', action='store_true')
        parser.add_argument('--title')
        parser.add_argument('-U', '--update-related-descriptions', action='store_true')
        parser.add_argument('--with-urls', action='store_true')
        parser.add_argument('-y', '--yes', action='store_true')

    add_code_hosting_parser('github', 'pr', include_sync=True)
    add_code_hosting_parser('gitlab', 'mr', include_sync=False)

    go_parser = create_subparser('go', alias='g')
    go_parser.add_argument('direction', nargs='?', default=None, metavar='go direction', choices=[
        'd', 'down', 'f', 'first', 'l', 'last', 'n', 'next',
        'p', 'prev', 'r', 'root', 'u', 'up']
    )

    help_parser = create_subparser('help')
    help_parser.add_argument('topic_or_cmd', nargs='?', choices=commands_and_aliases, default=None)

    is_managed_parser = create_subparser('is-managed')
    is_managed_parser.add_argument('branch', nargs='?')

    list_parser = create_subparser('list')
    list_parser.add_argument(
        'category',
        choices=[
            'addable', 'childless', 'managed', 'slidable', 'slidable-after', 'unmanaged',
            'with-overridden-fork-point']
    )
    list_parser.add_argument('branch', nargs='?')

    log_parser = create_subparser('log', alias='l')
    log_parser.add_argument('branch', nargs='?')

    reapply_parser = create_subparser('reapply')
    reapply_parser.add_argument('-f', '--fork-point')

    rename_parser = create_subparser('rename')
    rename_parser.add_argument('new_name')
    rename_parser.add_argument('-b', '--branch')
    rename_parser.add_argument('--repoint-tracking', action='store_true')

    show_parser = create_subparser('show')
    show_parser.add_argument('direction', metavar='show direction', choices=[
        'c', 'current', 'd', 'down', 'f', 'first', 'l', 'last',
        'n', 'next', 'p', 'prev', 'r', 'root', 'u', 'up']
    )
    show_parser.add_argument('branch', nargs='?')

    slide_out_parser = create_subparser('slide-out')
    slide_out_parser.add_argument('branches', nargs='*')
    slide_out_parser.add_argument('-d', '--down-fork-point')
    slide_out_parser.add_argument('--delete', action='store_true')
    slide_out_parser.add_argument('-M', '--merge', action='store_true')
    slide_out_parser.add_argument('-n', action='store_true')
    slide_out_parser.add_argument('--no-edit-merge', action='store_true')
    slide_out_parser.add_argument('--no-interactive-rebase', action='store_true')
    slide_out_parser.add_argument('--no-rebase', action='store_true')
    slide_out_parser.add_argument('--removed-from-remote', action='store_true')

    squash_parser = create_subparser('squash')
    squash_parser.add_argument('-f', '--fork-point')

    status_parser = create_subparser('status', alias='s')
    status_parser.add_argument('--color', choices=['always', 'auto', 'never'], default='auto')
    status_parser.add_argument('-l', '--list-commits', action='store_true')
    status_parser.add_argument('-L', '--list-commits-with-hashes', action='store_true')
    status_parser.add_argument('--no-detect-squash-merges', action='store_true')
    status_parser.add_argument('--squash-merge-detection')

    traverse_parser = create_subparser('traverse', alias='t')
    traverse_parser.add_argument('-F', '--fetch', action='store_true')
    traverse_parser.add_argument('-H', '--sync-github-prs', action='store_true')
    traverse_parser.add_argument('-l', '--list-commits', action='store_true')
    traverse_parser.add_argument('-L', '--sync-gitlab-mrs', action='store_true')
    traverse_parser.add_argument('-M', '--merge', action='store_true')
    traverse_parser.add_argument('-n', action='store_true')
    traverse_parser.add_argument('--no-detect-squash-merges', action='store_true')
    traverse_parser.add_argument('--no-edit-merge', action='store_true')
    traverse_parser.add_argument('--no-interactive-rebase', action='store_true')
    traverse_parser.add_argument('--no-push', action='store_true')
    traverse_parser.add_argument('--no-push-untracked', action='store_true')
    traverse_parser.add_argument('--push', action='store_true')
    traverse_parser.add_argument('--push-untracked', action='store_true')
    traverse_parser.add_argument('--return-to')
    traverse_parser.add_argument('--squash-merge-detection')
    traverse_parser.add_argument('--start-from')
    traverse_parser.add_argument('--stop-after')
    traverse_parser.add_argument('-W', action='store_true')
    traverse_parser.add_argument('-w', '--whole', action='store_true')
    traverse_parser.add_argument('-y', '--yes', action='store_true')

    update_parser = create_subparser('update')
    update_parser.add_argument('-f', '--fork-point')
    update_parser.add_argument('-M', '--merge', action='store_true')
    update_parser.add_argument('-n', action='store_true')
    update_parser.add_argument('--no-edit-merge', action='store_true')
    update_parser.add_argument('--no-interactive-rebase', action='store_true')

    create_subparser('version')

    return cli_parser


def update_cli_options_using_parsed_args(
        cli_opts: git_machete.options.CommandLineOptions,
        parsed_args: argparse.Namespace) -> None:
    # Warning: in mypy, arguments that come from untyped functions/variables are silently treated by mypy as Any.
    # Since argparse is not typed, everything that comes from argparse.Namespace will be taken as Any :(
    # Even if we add type=LocalBranchShortName into argument parser for branch,
    # python debugger will see branch as LocalBranchShortName but mypy always will see it as Any,
    # until you specifically tell mypy what is the exact type by casting
    # (right now it's done this way below, but casting does not solve all of the problems).
    #
    # The reasonable solution here would be to use Typed Argument Parser
    # which is a wrapper over argparse with modernised solution for typing.
    # But it would add external dependency to git-machete, so let's stick to current casting.

    for opt, arg in vars(parsed_args).items():
        # --color, --debug and --verbose are handled outside this method
        if opt == "all":
            cli_opts.opt_all = True
        elif opt == "as_first_child":
            cli_opts.opt_as_first_child = True
        elif opt == "as_root":
            cli_opts.opt_as_root = True
        elif opt == "base":
            cli_opts.opt_base = LocalBranchShortName.of(arg) if arg else None
        elif opt == "branch":
            cli_opts.opt_branch = LocalBranchShortName.of(arg.replace('refs/heads/', '')) if arg else None
        elif opt == "by":
            cli_opts.opt_by = arg
        elif opt == "checked_out_since":
            cli_opts.opt_checked_out_since = arg
        elif opt == "delete":
            cli_opts.opt_delete = True
        elif opt == "down_fork_point":
            cli_opts.opt_down_fork_point = AnyRevision.of(arg) if arg else None
        elif opt == "draft":
            cli_opts.opt_draft = True
        elif opt == "explain":
            cli_opts.opt_explain = True
        elif opt == "fetch":
            cli_opts.opt_fetch = True
        elif opt == "fork_point":
            cli_opts.opt_fork_point = AnyRevision.of(arg) if arg else None
        elif opt == "ignore_if_missing":
            cli_opts.opt_ignore_if_missing = True
        elif opt == "inferred":
            cli_opts.opt_inferred = True
        elif opt == "list_commits":
            cli_opts.opt_list_commits = True
        elif opt == "list_commits_with_hashes":
            cli_opts.opt_list_commits = cli_opts.opt_list_commits_with_hashes = True
        elif opt == "merge":
            cli_opts.opt_merge = True
        elif opt == "mine":
            cli_opts.opt_mine = True
        elif opt == "n":
            cli_opts.opt_n = True
        elif opt == "no_detect_squash_merges":
            warn("`--no-detect-squash-merges` is deprecated, use `--squash-merge-detection=none` instead\n")
            cli_opts.opt_squash_merge_detection_string = "none"
            cli_opts.opt_squash_merge_detection_origin = "`--no-detect-squash-merges` flag"
        elif opt == "no_edit_merge":
            cli_opts.opt_no_edit_merge = True
        elif opt == "no_interactive_rebase":
            cli_opts.opt_no_interactive_rebase = True
        elif opt == "no_push":
            cli_opts.opt_push_tracked = False
            cli_opts.opt_push_untracked = False
        elif opt == "no_push_untracked":
            cli_opts.opt_push_untracked = False
        elif opt == "no_rebase":
            cli_opts.opt_no_rebase = True
        elif opt == "onto":
            cli_opts.opt_onto = LocalBranchShortName.of(arg) if arg else None
        elif opt == "override_to":
            cli_opts.opt_override_to = arg
        elif opt == "override_to_inferred":
            cli_opts.opt_override_to_inferred = True
        elif opt == "override_to_parent":
            cli_opts.opt_override_to_parent = True
        elif opt == "push":
            cli_opts.opt_push_tracked = True
            cli_opts.opt_push_untracked = True
        elif opt == "push_untracked":
            cli_opts.opt_push_untracked = True
        elif opt == "related":
            cli_opts.opt_related = True
        elif opt == "repoint_tracking":
            cli_opts.opt_repoint_tracking = True
        elif opt == "removed_from_remote":
            cli_opts.opt_removed_from_remote = True
        elif opt == "return_to":
            cli_opts.opt_return_to = arg
        elif opt == "roots":
            roots: Iterable[str] = filter(None, arg.split(","))
            cli_opts.opt_roots = [LocalBranchShortName.of(root) for root in roots]
        elif opt == "squash_merge_detection" and arg is not None:  # if no arg is passed, argparse will fail anyway
            cli_opts.opt_squash_merge_detection_string = arg
            cli_opts.opt_squash_merge_detection_origin = "`--squash-merge-detection` flag"
        elif opt == "start_from":
            cli_opts.opt_start_from = arg
        elif opt == "stat":
            cli_opts.opt_stat = True
        elif opt == "stop_after":
            cli_opts.opt_stop_after = LocalBranchShortName.of(arg) if arg else None
        elif opt == "sync_github_prs":
            cli_opts.opt_sync_github_prs = True
        elif opt == "sync_gitlab_mrs":
            cli_opts.opt_sync_gitlab_mrs = True
        elif opt == "title":
            cli_opts.opt_title = arg
        elif opt == "unset_override":
            cli_opts.opt_unset_override = True
        elif opt == "update_related_descriptions":
            cli_opts.opt_update_related_descriptions = True
        elif opt == "W":
            cli_opts.opt_fetch = True
            cli_opts.opt_start_from = "first-root"
            cli_opts.opt_n = True
            cli_opts.opt_return_to = "nearest-remaining"
        elif opt == "whole":
            cli_opts.opt_start_from = "first-root"
            cli_opts.opt_n = True
            cli_opts.opt_return_to = "nearest-remaining"
        elif opt == "with_urls":
            cli_opts.opt_with_urls = True
        elif opt == "yes":
            cli_opts.opt_yes = True

    if cli_opts.opt_n or cli_opts.opt_yes:
        # Set no-edit-merge as the default, as some branches might have a merge strategy even without --merge set
        cli_opts.opt_no_edit_merge = True
    if not cli_opts.opt_merge:
        if cli_opts.opt_yes or cli_opts.opt_n:
            cli_opts.opt_no_interactive_rebase = True


def update_cli_options_using_config_keys(
        cli_opts: git_machete.options.CommandLineOptions,
        git: Git
) -> None:
    traverse_push = MacheteConfig(git).traverse_push()
    if traverse_push is not None:
        cli_opts.opt_push_tracked = cli_opts.opt_push_untracked = traverse_push


def set_utils_global_variables(parsed_args: argparse.Namespace) -> None:
    args = vars(parsed_args)
    color = args.get("color")
    markup.use_ansi_escapes_in_stdout = color == "always" or (color in {None, "auto"} and terminal.is_stdout_a_tty())
    markup.use_ansi_escapes_in_stderr = color == "always" or (color in {None, "auto"} and terminal.is_stderr_a_tty())
    debug_log.debug_mode = "debug" in args
    cmd.verbose_mode = "verbose" in args


def launch(orig_args: List[str]) -> None:
    try:
        launch_internal(orig_args)
    except InteractionStopped:
        pass


def launch_internal(orig_args: List[str]) -> None:
    initial_current_directory: Optional[str] = get_current_directory_or_none()

    try:
        cli_opts = git_machete.options.CommandLineOptions()
        git = Git()

        direct_args = list(itertools.takewhile(lambda arg: arg != "--", orig_args))
        pass_through_args = list(itertools.dropwhile(lambda arg: arg != "--", orig_args))
        cli_parser: argparse.ArgumentParser = create_cli_parser()
        parsed_cli: argparse.Namespace = cli_parser.parse_args(direct_args)
        parsed_cli_as_dict: Dict[str, Any] = vars(parsed_cli)

        # Let's set up options like debug/verbose before we first start reading `git config`.
        set_utils_global_variables(parsed_cli)
        update_cli_options_using_config_keys(cli_opts, git)
        update_cli_options_using_parsed_args(cli_opts, parsed_cli)

        if cli_opts.opt_no_interactive_rebase and cli_opts.opt_merge:
            raise MacheteException(
                "Option `--no-interactive-rebase` only makes sense when using "
                "rebase and cannot be specified together with `-M/--merge`.")
        if cli_opts.opt_fork_point and cli_opts.opt_merge:
            raise MacheteException(
                "Option `-f/--fork-point` only makes sense when using rebase and"
                " cannot be specified together with `-M/--merge`.")
        if cli_opts.opt_sync_github_prs and cli_opts.opt_sync_gitlab_mrs:
            raise MacheteException(
                "Option `-H/--sync-github-prs` cannot be specified together with `-L/--sync-gitlab-mrs`.")

        cmd = parsed_cli.command
        if not cmd:
            print_fmt(get_help_description(display_help_topics=False))
            sys.exit(ExitCode.ARGUMENT_ERROR)

        if cmd not in ("d", "diff", "l", "log") and pass_through_args:
            print_fmt("Extra arguments after `--` are only allowed after `diff` and `log`")
            sys.exit(ExitCode.ARGUMENT_ERROR)
        if pass_through_args and pass_through_args[0] == "--":
            pass_through_args = pass_through_args[1:]

        def squash_merge_detection() -> SquashMergeDetection:
            if cli_opts.opt_squash_merge_detection_origin is not None:
                return SquashMergeDetection.from_string(
                    cli_opts.opt_squash_merge_detection_string, cli_opts.opt_squash_merge_detection_origin)
            return MacheteConfig(git).squash_merge_detection()

        if cmd == "completion":
            completion_shell = parsed_cli.shell

            def print_completion_resource(name: str) -> None:
                data = pkgutil.get_data("completion", name)
                if not data:
                    raise UnexpectedMacheteException(f"Completion file `{name}` not found.")
                print(data.decode())

            # Deliberately using if/else instead of a dict - to measure coverage more accurately.
            if completion_shell == "bash":
                print_completion_resource("git-machete.completion.bash")
            elif completion_shell == "fish":
                print_completion_resource("git-machete.fish")
            elif completion_shell == "zsh":  # an unknown shell is handled by argparse
                print_completion_resource("git-machete.completion.zsh")
            else:  # an unknown shell is handled by argparse
                raise UnexpectedMacheteException(f"Unknown shell: `{completion_shell}`")
            return
        elif cmd == "help":
            print_fmt(get_help_description(display_help_topics=True, command=parsed_cli.topic_or_cmd))
            return
        elif cmd == "version":
            version()
            return

        if cmd == "add":
            if cli_opts.opt_as_root and cli_opts.opt_onto:
                raise MacheteException("Option `-R/--as-root` cannot be specified together with `-o/--onto`.")
            if cli_opts.opt_as_root and cli_opts.opt_as_first_child:
                raise MacheteException("Option `-R/--as-root` cannot be specified together with `-f/--as-first-child`.")
            add_client = MacheteClient(git)
            add_client.read_branch_layout_file()
            branch = cli_opts.opt_branch or git.get_current_branch()
            add_client.add(
                branch=branch,
                opt_onto=cli_opts.opt_onto,
                opt_as_first_child=cli_opts.opt_as_first_child,
                opt_as_root=cli_opts.opt_as_root,
                opt_yes=cli_opts.opt_yes,
                verbose=True,
                switch_head_if_new_branch=True)
        elif cmd == "advance":
            advance_client = AdvanceMacheteClient(git)
            advance_client.read_branch_layout_file()
            advance_client.advance(opt_yes=cli_opts.opt_yes)
        elif cmd == "anno":
            spec = GITHUB_API_SPEC if cli_opts.opt_sync_github_prs else GITLAB_API_SPEC
            anno_client = AnnoMacheteClient(git, spec)
            anno_client.read_branch_layout_file(verify_branches=False)
            if cli_opts.opt_sync_github_prs or cli_opts.opt_sync_gitlab_mrs:
                anno_client.sync_annotations_to_prs(include_urls=False)
            else:
                branch = cli_opts.opt_branch or git.get_current_branch()
                anno_client.expect_in_managed_branches(branch)
                if 'annotation_text' in parsed_cli:
                    anno_client.annotate(branch, parsed_cli.annotation_text)
                else:
                    anno_client.print_annotation(branch)
        elif cmd == "clean":
            clean_client = MacheteClientWithCodeHosting(git, GITHUB_API_SPEC)
            clean_client.read_branch_layout_file()
            if 'checkout_my_github_prs' in parsed_cli:
                clean_client.checkout_pull_requests(pr_numbers=[], mine=True)
            clean_client.delete_unmanaged(opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=cli_opts.opt_yes)
            clean_client.delete_untracked(opt_yes=cli_opts.opt_yes)
        elif cmd == "delete-unmanaged":
            delete_unmanaged_client = MacheteClient(git)
            delete_unmanaged_client.read_branch_layout_file()
            delete_unmanaged_client.delete_unmanaged(
                opt_squash_merge_detection=MacheteConfig(git).squash_merge_detection(),
                opt_yes=cli_opts.opt_yes)
        elif cmd in {"diff", alias_by_command["diff"]}:
            diff_client = DiffMacheteClient(git)
            diff_client.read_branch_layout_file()
            diff_client.display_diff(branch=cli_opts.opt_branch, opt_stat=cli_opts.opt_stat, extra_git_diff_args=pass_through_args)
        elif cmd == "discover":
            discover_client = DiscoverMacheteClient(git)
            discover_client.read_branch_layout_file()
            discover_client.discover(
                opt_checked_out_since=cli_opts.opt_checked_out_since,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_roots=cli_opts.opt_roots,
                opt_yes=cli_opts.opt_yes)
        elif cmd in {"edit", alias_by_command["edit"]}:
            # No need to read branch layout file.
            edit_client = MacheteClient(git)
            edit_client.edit()
        elif cmd == "file":
            # No need to read branch layout file.
            file_client = MacheteClient(git)
            print(abspath_posix(file_client.branch_layout_file_path))
        elif cmd == "fork-point":
            fork_point_client = ForkPointMacheteClient(git)
            fork_point_client.read_branch_layout_file()
            branch = cli_opts.opt_branch or git.get_current_branch()
            parent = fork_point_client.parent_of(branch)
            fork_point_client.expect_in_local_branches(branch)

            def warn_on_deprecation(*, flag: str, revision: AnyRevision, revision_str: str) -> None:
                if parent:
                    print()
                    warn(
                        f"`git machete fork-point {flag}` may lead to a confusing user experience and is deprecated.\n\n"
                        f"If the commits between <b>{parent}</b> (parent of <b>{branch}</b>) "
                        f"and {revision_str} <b>{git.get_short_commit_hash_by_revision_or_none(revision) or ''}</b> "
                        f"do NOT belong to <b>{branch}</b>, consider using:\n"
                        f"    `git checkout {branch}`\n"
                        f"    `git machete update --fork-point=\"{revision}\"`\n\n"
                        "Otherwise, if you're okay with treating these commits "
                        f"as a part of <b>{branch}</b>'s unique history, use instead:\n"
                        f"    `git machete fork-point {branch} --override-to-parent`"
                    )
                # It's unlikely that anyone overrides fork point for a branch that doesn't have a parent,
                # also it's unclear what the suggested action should even be - let's skip this case.

            if cli_opts.opt_override_to or cli_opts.opt_override_to_inferred or \
                    cli_opts.opt_override_to_parent or cli_opts.opt_unset_override:
                if cli_opts.opt_explain:
                    raise MacheteException(
                        "`--explain` cannot be combined with "
                        "`--override-to`/`--override-to-inferred`/`--override-to-parent`/`--unset-override`.")

            if cli_opts.opt_inferred:
                fork_point_client.print_fork_point(branch=branch, use_overrides=False, explain=cli_opts.opt_explain)
            elif cli_opts.opt_override_to:
                override_to = AnyRevision.of(cli_opts.opt_override_to)
                fork_point_client.set_fork_point_override(branch, override_to)
                # Let's issue the warning only if there are no errors from set_fork_point_override.
                warn_on_deprecation(
                    flag="--override-to=...",
                    revision=override_to,
                    revision_str="selected commit")
            elif cli_opts.opt_override_to_inferred:
                fork_point = fork_point_client.fork_point(branch=branch, use_overrides=False)
                fork_point_client.set_fork_point_override(branch, fork_point)
                warn_on_deprecation(
                    flag="--override-to-inferred",
                    revision=fork_point,
                    revision_str="inferred commit")
            elif cli_opts.opt_override_to_parent:
                if parent:
                    fork_point_client.set_fork_point_override(branch, parent)
                else:
                    raise MacheteException(
                        f"Branch <b>{branch}</b> does not have upstream (parent) branch")
            elif cli_opts.opt_unset_override:
                fork_point_client.unset_fork_point_override(branch)
            else:
                fork_point_client.print_fork_point(branch=branch, use_overrides=True, explain=cli_opts.opt_explain)
        elif cmd in {"github", "gitlab"}:
            subcommand = parsed_cli.subcommand
            spec = GITHUB_API_SPEC if cmd == "github" else GITLAB_API_SPEC
            pr_or_mr = spec.pr_short_name.lower()

            if "request_id" in parsed_cli and subcommand != f"checkout-{pr_or_mr}s":
                raise MacheteException(f"{spec.pr_short_name} number is only valid with `checkout-{pr_or_mr}s` subcommand.")
            for name, value in (("all", cli_opts.opt_all), ("mine", cli_opts.opt_mine)):
                if value and subcommand not in (f"checkout-{pr_or_mr}s", f"update-{pr_or_mr}-descriptions"):
                    raise MacheteException(f"`--{name}` option is only valid with "
                                           f"`checkout-{pr_or_mr}s` and `update-{pr_or_mr}-descriptions` subcommands.")
            if cli_opts.opt_branch is not None and subcommand != f"retarget-{pr_or_mr}":
                raise MacheteException(f"`--branch` option is only valid with `retarget-{pr_or_mr}` subcommand.")
            if cli_opts.opt_by is not None and subcommand not in (f"checkout-{pr_or_mr}s", f"update-{pr_or_mr}-descriptions"):
                raise MacheteException(f"`--by` option is only valid with "
                                       f"`checkout-{pr_or_mr}s` and `update-{pr_or_mr}-descriptions` subcommands.")
            if cli_opts.opt_draft and subcommand != f"create-{pr_or_mr}":
                raise MacheteException(f"`--draft` option is only valid with `create-{pr_or_mr}` subcommand.")
            if cli_opts.opt_ignore_if_missing and subcommand != f"retarget-{pr_or_mr}":
                raise MacheteException(f"`--ignore-if-missing` option is only valid with `retarget-{pr_or_mr}` subcommand.")
            if cli_opts.opt_related and subcommand != f"update-{pr_or_mr}-descriptions":
                raise MacheteException(f"`--related` option is only valid with `update-{pr_or_mr}-descriptions` subcommand.")
            if cli_opts.opt_title is not None and subcommand != f"create-{pr_or_mr}":
                raise MacheteException(f"`--title` option is only valid with `create-{pr_or_mr}` subcommand.")
            if (cli_opts.opt_update_related_descriptions and
                    subcommand not in (f"create-{pr_or_mr}", f"restack-{pr_or_mr}", f"retarget-{pr_or_mr}")):
                raise MacheteException(f"`--update-related-descriptions` option is only valid "
                                       f"with `create-{pr_or_mr}`, `restack-{pr_or_mr}` and `retarget-{pr_or_mr}` subcommands.")
            if cli_opts.opt_with_urls and subcommand != f"anno-{pr_or_mr}s":
                raise MacheteException(f"`--with-urls` option is only valid with `anno-{pr_or_mr}s` subcommand.")
            if cli_opts.opt_yes and subcommand != f"create-{pr_or_mr}":
                raise MacheteException(f"`--yes` option is only valid with `create-{pr_or_mr}` subcommand.")

            github_or_gitlab_client = MacheteClientWithCodeHosting(git, spec)
            github_or_gitlab_client.read_branch_layout_file()

            if subcommand == f"anno-{pr_or_mr}s":
                github_or_gitlab_client.sync_annotations_to_prs(include_urls=cli_opts.opt_with_urls)
            elif subcommand == f"checkout-{pr_or_mr}s":
                if len(set(parsed_cli_as_dict.keys()).intersection({'all', 'by', 'mine', 'request_id'})) != 1:
                    raise MacheteException(
                        f"`checkout-{pr_or_mr}s` subcommand must take exactly one of the following options: "
                        f'`--all`, `--by=...`, `--mine`, `{pr_or_mr}-number(s)`')
                github_or_gitlab_client.checkout_pull_requests(
                    pr_numbers=parsed_cli.request_id if 'request_id' in parsed_cli else [],
                    all=cli_opts.opt_all,
                    mine=cli_opts.opt_mine,
                    by=cli_opts.opt_by,
                    fail_on_missing_current_user_for_my_open_prs=True)
            elif subcommand == f"create-{pr_or_mr}":
                current_branch = git.get_current_branch()
                github_or_gitlab_client.sync_before_creating_pull_request(opt_yes=cli_opts.opt_yes)
                github_or_gitlab_client.create_pull_request(
                    head=current_branch,
                    opt_base=cli_opts.opt_base,
                    opt_draft=cli_opts.opt_draft,
                    opt_title=cli_opts.opt_title,
                    opt_update_related_descriptions=cli_opts.opt_update_related_descriptions,
                    opt_yes=cli_opts.opt_yes)
            elif subcommand == f"restack-{pr_or_mr}":
                github_or_gitlab_client.restack_pull_request(opt_update_related_descriptions=cli_opts.opt_update_related_descriptions)
            elif subcommand == f"retarget-{pr_or_mr}":
                branch = cli_opts.opt_branch or git.get_current_branch()
                github_or_gitlab_client.expect_in_managed_branches(branch)
                github_or_gitlab_client.retarget_pull_request(
                    head=branch,
                    opt_ignore_if_missing=cli_opts.opt_ignore_if_missing,
                    opt_update_related_descriptions=cli_opts.opt_update_related_descriptions
                )
            elif subcommand == "sync":  # GitHub only
                github_or_gitlab_client.checkout_pull_requests(pr_numbers=[], mine=True)
                github_or_gitlab_client.delete_unmanaged(opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=False)
                github_or_gitlab_client.delete_untracked(opt_yes=cli_opts.opt_yes)
            elif subcommand == f"update-{pr_or_mr}-descriptions":
                selectors = set(parsed_cli_as_dict.keys()).intersection({'all', 'by', 'mine', 'related'})
                if len(selectors) > 1:
                    raise MacheteException(
                        f"`update-{pr_or_mr}-descriptions` subcommand takes at most one of the following options: "
                        '`--all`, `--by=...`, `--mine`, `--related`; '
                        '`--related` is assumed if none of these is provided.')
                related = cli_opts.opt_related or not selectors
                github_or_gitlab_client.update_pull_request_descriptions(
                    all=cli_opts.opt_all, by=cli_opts.opt_by, mine=cli_opts.opt_mine, related=related)
            else:  # an unknown subcommand is handled by argparse
                raise UnexpectedMacheteException(f"Unknown subcommand: `{subcommand}`")
        elif cmd in {"go", alias_by_command["go"]}:
            git.expect_no_operation_in_progress()
            current_branch_or_none = git.get_current_branch_or_none()

            if parsed_cli.direction is not None:
                go_client = GoShowMacheteClient(git)
                go_client.read_branch_layout_file()
                # with pick_if_multiple=True, there returned list will have exactly one element
                dest = go_client.parse_direction(
                    parsed_cli.direction, branch=current_branch_or_none,
                    allow_current=False, pick_if_multiple=True)[0]
                if dest != current_branch_or_none:
                    print_fmt(f"Checking out <b>{dest}</b>... ", newline=False)
                    git.checkout(dest)
                    print_fmt(green_ok())
            else:
                interactive_client = GoInteractiveMacheteClient(git)
                interactive_client.read_branch_layout_file()
                interactive_client.expect_at_least_one_managed_branch()
                selected_branch = interactive_client.go_interactive(current_branch=current_branch_or_none)
                if selected_branch is not None and selected_branch != current_branch_or_none:
                    print()
                    print_fmt(f"Checking out <b>{selected_branch}</b>... ", newline=False)
                    git.checkout(selected_branch)
                    print_fmt(green_ok())
        elif cmd == "is-managed":
            is_managed_client = MacheteClient(git)
            is_managed_client.read_branch_layout_file()
            branch = cli_opts.opt_branch or git.get_current_branch()
            if branch is None or branch not in is_managed_client.managed_branches:
                sys.exit(ExitCode.MACHETE_EXCEPTION)
        elif cmd == "list":
            category = parsed_cli.category
            if category == 'slidable-after' and not cli_opts.opt_branch:
                raise MacheteException(f"`git machete list {category}` requires an extra <branch> argument")
            elif category != 'slidable-after' and cli_opts.opt_branch:
                raise MacheteException(f"`git machete list {category}` does not expect extra arguments")

            list_client = ListMacheteClient(git)
            list_client.read_branch_layout_file()
            res = []
            if category == "addable":
                res = list_client.addable_branches()
            elif category == "childless":
                res = list_client.childless_managed_branches()
            elif category == "managed":
                res = list_client.managed_branches
            elif category == "slidable":
                res = list_client.slidable_branches()
            elif category == "slidable-after":
                list_client.expect_in_managed_branches(parsed_cli.branch)
                res = list_client.get_slidable_after(parsed_cli.branch)
            elif category == "unmanaged":
                res = list_client.unmanaged_branches()
            elif category == "with-overridden-fork-point":
                res = list_client.branches_with_overridden_fork_point()
            else:  # an unknown category is handled by argparse
                raise UnexpectedMacheteException(f"Invalid category: `{category}`")

            if res:
                print("\n".join(res))
        elif cmd in {"log", alias_by_command["log"]}:
            log_client = LogMacheteClient(git)
            log_client.read_branch_layout_file()
            branch = cli_opts.opt_branch or git.get_current_branch()
            log_client.display_log(branch, extra_git_log_args=pass_through_args)
        elif cmd == "reapply":
            reapply_client = ReapplyMacheteClient(git)
            reapply_client.read_branch_layout_file()
            reapply_client.reapply(
                opt_fork_point=cli_opts.opt_fork_point,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase)
        elif cmd == "rename":
            rename_client = RenameMacheteClient(git)
            rename_client.read_branch_layout_file()
            branch = cli_opts.opt_branch or git.get_current_branch()
            rename_client.rename(
                branch=branch,
                new_name=LocalBranchShortName.of(parsed_cli.new_name),
                opt_repoint_tracking=cli_opts.opt_repoint_tracking)
        elif cmd == "show":
            direction = parsed_cli.direction
            if direction == "current" and cli_opts.opt_branch:
                raise MacheteException('`show current` with a `<branch>` argument does not make sense')
            branch = cli_opts.opt_branch or git.get_current_branch()
            show_client = GoShowMacheteClient(git)
            show_client.read_branch_layout_file(verify_branches=False)
            print('\n'.join(show_client.parse_direction(direction, branch=branch, allow_current=True, pick_if_multiple=False)))
        elif cmd == "slide-out":
            if cli_opts.opt_down_fork_point and cli_opts.opt_merge:
                raise MacheteException(
                    "Option `-d/--down-fork-point` only makes sense when using "
                    "rebase and cannot be specified together with `-M/--merge`.")
            if cli_opts.opt_down_fork_point and cli_opts.opt_no_rebase:
                raise MacheteException(
                    "Option `-d/--down-fork-point` only makes sense when using "
                    "rebase and cannot be specified together with `--no-rebase`.")
            if cli_opts.opt_merge and cli_opts.opt_no_rebase:
                raise MacheteException(
                    "Option `-M/--merge` cannot be specified together with `--no-rebase`.")
            if cli_opts.opt_no_interactive_rebase and cli_opts.opt_no_rebase:
                raise MacheteException(
                    "Option `--no-interactive-rebase` only makes sense when using "
                    "rebase and cannot be specified together with `--no-rebase`.")
            if cli_opts.opt_no_edit_merge and cli_opts.opt_no_rebase:
                raise MacheteException(
                    "Option `--no-edit-merge` only makes sense when using "
                    "merge and cannot be specified together with `--no-rebase`.")

            slide_out_client = SlideOutMacheteClient(git)
            slide_out_client.read_branch_layout_file()
            branches_to_slide_out: Optional[List[str]] = parsed_cli_as_dict.get('branches')
            if cli_opts.opt_removed_from_remote:
                if (branches_to_slide_out or cli_opts.opt_down_fork_point or cli_opts.opt_merge or
                        cli_opts.opt_no_interactive_rebase or cli_opts.opt_no_rebase):
                    raise MacheteException("Only `--delete` can be passed with `--removed-from-remote`")
                slide_out_client.slide_out_removed_from_remote(opt_delete=cli_opts.opt_delete)
            else:
                slide_out_client.slide_out(
                    branches_to_slide_out=[LocalBranchShortName.of(branch)
                                           for branch in (branches_to_slide_out or [git.get_current_branch()])],
                    opt_delete=cli_opts.opt_delete,
                    opt_down_fork_point=cli_opts.opt_down_fork_point,
                    opt_merge=cli_opts.opt_merge,
                    opt_no_edit_merge=cli_opts.opt_no_edit_merge,
                    opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                    opt_no_rebase=cli_opts.opt_no_rebase)
        elif cmd == "squash":
            squash_client = SquashMacheteClient(git)
            squash_client.read_branch_layout_file()
            squash_client.squash(
                current_branch=git.get_current_branch(),
                opt_fork_point=cli_opts.opt_fork_point)
        elif cmd in {"status", alias_by_command["status"]}:
            opt_squash_merge_detection = squash_merge_detection()
            status_client = StatusMacheteClient(git)
            status_client.read_branch_layout_file(interactively_slide_out_invalid_branches=terminal.is_stdout_a_tty())
            status_client.expect_at_least_one_managed_branch()
            status_client.status(
                warn_when_branch_in_sync_but_fork_point_off=True,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_list_commits_with_hashes=cli_opts.opt_list_commits_with_hashes,
                opt_squash_merge_detection=opt_squash_merge_detection)
        elif cmd in {"traverse", alias_by_command["traverse"]}:
            opt_squash_merge_detection = squash_merge_detection()
            opt_return_to = TraverseReturnTo.from_string(cli_opts.opt_return_to, "`--return-to` flag")
            opt_start_from = TraverseStartFrom.from_string_or_branch(cli_opts.opt_start_from, git)

            spec = GITHUB_API_SPEC if cli_opts.opt_sync_github_prs else GITLAB_API_SPEC
            traverse_client = TraverseMacheteClient(git, spec)
            traverse_client.read_branch_layout_file(interactively_slide_out_invalid_branches=terminal.is_stdout_a_tty())
            traverse_client.traverse(
                opt_fetch=cli_opts.opt_fetch,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_merge=cli_opts.opt_merge,
                opt_no_edit_merge=cli_opts.opt_no_edit_merge,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                opt_push_tracked=cli_opts.opt_push_tracked,
                opt_push_untracked=cli_opts.opt_push_untracked,
                opt_return_to=opt_return_to,
                opt_squash_merge_detection=opt_squash_merge_detection,
                opt_start_from=opt_start_from,
                opt_stop_after=cli_opts.opt_stop_after,
                opt_sync_github_prs=cli_opts.opt_sync_github_prs,
                opt_sync_gitlab_mrs=cli_opts.opt_sync_gitlab_mrs,
                opt_yes=cli_opts.opt_yes)
        elif cmd == "update":
            update_client = UpdateMacheteClient(git)
            update_client.read_branch_layout_file()
            update_client.update(
                opt_merge=cli_opts.opt_merge,
                opt_no_edit_merge=cli_opts.opt_no_edit_merge,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                opt_fork_point=cli_opts.opt_fork_point)
        else:  # an unknown command is handled by argparse
            raise UnexpectedMacheteException(f"Unknown command: `{cmd}`")
    finally:
        # Note that this problem (current directory no longer existing due to e.g. underlying git checkouts)
        # has been fixed in git itself as of 2.35.0:
        # see https://github.com/git/git/blob/master/Documentation/RelNotes/2.35.0.txt#L81
        if initial_current_directory and not does_directory_exist(initial_current_directory):
            nearest_existing_parent_directory = initial_current_directory
            while not does_directory_exist(nearest_existing_parent_directory):
                nearest_existing_parent_directory = join_paths_posix(
                    nearest_existing_parent_directory, os.path.pardir)
            warn(f"current directory {initial_current_directory} no longer exists, "
                 f"the nearest existing parent directory is {abspath_posix(nearest_existing_parent_directory)}")


def main() -> None:
    try:
        launch(sys.argv[1:])
    except EOFError:  # pragma: no cover
        sys.exit(ExitCode.END_OF_FILE_SIGNAL)
    except KeyboardInterrupt:
        sys.exit(ExitCode.KEYBOARD_INTERRUPT)
    except (MacheteException, UnderlyingGitException) as e:
        print(e, file=sys.stderr)
        sys.exit(ExitCode.MACHETE_EXCEPTION)


if __name__ == "__main__":
    main()
