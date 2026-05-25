#!/usr/bin/env python3

import pkgutil
import sys
from typing import Iterable, List, Optional, Sequence

import git_machete.options
from git_machete.cli_parser import ParsedCmd, parse_cmdline
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
from git_machete.client.traverse import TraverseMacheteClient, TraverseReturnTo
from git_machete.client.update import UpdateMacheteClient
from git_machete.client.with_code_hosting import MacheteClientWithCodeHosting
from git_machete.config import SquashMergeDetection
from git_machete.git import AnyRevision, LocalBranchShortName
from git_machete.github import GITHUB_API_SPEC
from git_machete.gitlab import GITLAB_API_SPEC
from git_machete.help import alias_by_command, get_help_description, version
from git_machete.utils import cmd, debug_log, markup, terminal
from git_machete.utils.exceptions import (ExitCode, InteractionStopped,
                                          MacheteException,
                                          UnderlyingGitException,
                                          UnexpectedMacheteException)
from git_machete.utils.fs import (does_directory_exist,
                                  get_current_directory_or_none)
from git_machete.utils.markup import print_fmt, warn
from git_machete.utils.paths import AbsPath


def _populate_cli_options(
        cli_opts: git_machete.options.CommandLineOptions,
        parsed: ParsedCmd,
) -> None:
    """Translate the raw `ParsedCmd` (flags as strings, positionals keyed by display name) into the typed `CommandLineOptions` aggregate.

    Options are processed in user-input order so that "last one wins" works intuitively:
    `git machete traverse -W --start-from=here` overrides the `start-from` baked into the `-W` macro
    because `--start-from=here` is seen later in the command line. Same goes for `--push` after `--no-push`.

    This is also the only place that knows how to coerce raw strings into the project's domain types
    (`LocalBranchShortName`, `AnyRevision`, comma-separated `--roots`, the `-W` macro that fans out to four other flags, ...).
    """
    branch_positional: Optional[str] = parsed.positionals.get("branch")
    if branch_positional:
        cli_opts.opt_branch = LocalBranchShortName.of(
            branch_positional.replace("refs/heads/", ""))

    for key, value in parsed.opts.items():
        if key == "all":
            cli_opts.opt_all = True
        elif key == "as-first-child":
            cli_opts.opt_as_first_child = True
        elif key == "as-root":
            cli_opts.opt_as_root = True
        elif key == "base":
            cli_opts.opt_base = LocalBranchShortName.of(value) if value else None
        elif key == "branch":
            cli_opts.opt_branch = LocalBranchShortName.of(
                value.replace("refs/heads/", "")) if value else None
        elif key == "by":
            cli_opts.opt_by = value
        elif key == "checked-out-since":
            cli_opts.opt_checked_out_since = value
        elif key == "delete":
            cli_opts.opt_delete = True
        elif key == "down-fork-point":
            cli_opts.opt_down_fork_point = AnyRevision.of(value) if value else None
        elif key == "draft":
            cli_opts.opt_draft = True
        elif key == "explain":
            cli_opts.opt_explain = True
        elif key == "fetch":
            cli_opts.opt_fetch = True
        elif key == "fork-point":
            cli_opts.opt_fork_point = AnyRevision.of(value) if value else None
        elif key == "ignore-if-missing":
            cli_opts.opt_ignore_if_missing = True
        elif key == "inferred":
            cli_opts.opt_inferred = True
        elif key == "list-commits":
            cli_opts.opt_list_commits = True
        elif key == "list-commits-with-hashes":
            cli_opts.opt_list_commits = cli_opts.opt_list_commits_with_hashes = True
        elif key == "merge":
            cli_opts.opt_merge = True
        elif key == "mine":
            cli_opts.opt_mine = True
        elif key == "n":
            cli_opts.opt_n = True
        elif key == "no-detect-squash-merges":
            warn("`--no-detect-squash-merges` is deprecated, use `--squash-merge-detection=none` instead\n")
            cli_opts.opt_squash_merge_detection = SquashMergeDetection.NONE
        elif key == "no-edit-merge":
            cli_opts.opt_no_edit_merge = True
        elif key == "no-interactive-rebase":
            cli_opts.opt_no_interactive_rebase = True
        elif key == "no-push":
            cli_opts.opt_push_tracked = False
            cli_opts.opt_push_untracked = False
        elif key == "no-push-untracked":
            cli_opts.opt_push_untracked = False
        elif key == "no-rebase":
            cli_opts.opt_no_rebase = True
        elif key == "onto":
            cli_opts.opt_onto = LocalBranchShortName.of(value) if value else None
        elif key == "override-to":
            cli_opts.opt_override_to = value
        elif key == "override-to-inferred":
            cli_opts.opt_override_to_inferred = True
        elif key == "override-to-parent":
            cli_opts.opt_override_to_parent = True
        elif key == "push":
            cli_opts.opt_push_tracked = True
            cli_opts.opt_push_untracked = True
        elif key == "push-untracked":
            cli_opts.opt_push_untracked = True
        elif key == "related":
            cli_opts.opt_related = True
        elif key == "removed-from-remote":
            cli_opts.opt_removed_from_remote = True
        elif key == "repoint-tracking":
            cli_opts.opt_repoint_tracking = True
        elif key == "return-to":
            cli_opts.opt_return_to = value
        elif key == "roots":
            roots: Iterable[str] = filter(None, value.split(","))
            cli_opts.opt_roots = [LocalBranchShortName.of(root) for root in roots]
        elif key == "squash-merge-detection":
            cli_opts.opt_squash_merge_detection = SquashMergeDetection.from_string(
                value, "`--squash-merge-detection` flag")
        elif key == "start-from":
            cli_opts.opt_start_from = value
        elif key == "stat":
            cli_opts.opt_stat = True
        elif key == "stop-after":
            cli_opts.opt_stop_after = LocalBranchShortName.of(value) if value else None
        elif key == "sync-github-prs":
            cli_opts.opt_sync_github_prs = True
        elif key == "sync-gitlab-mrs":
            cli_opts.opt_sync_gitlab_mrs = True
        elif key == "title":
            cli_opts.opt_title = value
        elif key == "unset-override":
            cli_opts.opt_unset_override = True
        elif key == "update-related-descriptions":
            cli_opts.opt_update_related_descriptions = True
        elif key == "W":
            cli_opts.opt_fetch = True
            cli_opts.opt_start_from = "first-root"
            cli_opts.opt_n = True
            cli_opts.opt_return_to = "nearest-remaining"
        elif key == "whole":
            cli_opts.opt_start_from = "first-root"
            cli_opts.opt_n = True
            cli_opts.opt_return_to = "nearest-remaining"
        elif key == "with-urls":
            cli_opts.opt_with_urls = True
        elif key == "yes":
            cli_opts.opt_yes = True
        # `debug`, `verbose`, `color`, `help`, `version`, `checkout-my-github-prs`,
        # plus per-subcommand presence-only markers (`sync-github-prs` consumers of GitLab specs etc.)
        # are picked up directly from `parsed.opts` by the dispatcher below or by `set_utils_global_variables`.

    if cli_opts.opt_n or cli_opts.opt_yes:
        # Some branches may carry a merge strategy even when --merge isn't set,
        # so default-no-edit lines up with --yes/-n in those cases too.
        cli_opts.opt_no_edit_merge = True
    if not cli_opts.opt_merge:
        if cli_opts.opt_yes or cli_opts.opt_n:
            cli_opts.opt_no_interactive_rebase = True


def set_utils_global_variables(parsed: ParsedCmd) -> None:
    # Side effects are concentrated here (rather than scattered through `parse_cmdline`)
    # so that the parser stays free of global state mutation - it returns a plain `ParsedCmd` and lets the caller decide what to do with it.
    # `--color` is applied here even though it means parser-level `MacheteException`s (mutex / "only valid with X subcommand")
    # don't pick up `--color=always` / `--color=never` - those messages contain only minor markup (backticks)
    # and the default `--color=auto` behavior (TTY-detected at module import) already does the right thing in practice.
    color = parsed.opts.get("color")
    markup.use_ansi_escapes_in_stdout = color == "always" or (color in {None, "auto"} and terminal.is_stdout_a_tty())
    markup.use_ansi_escapes_in_stderr = color == "always" or (color in {None, "auto"} and terminal.is_stderr_a_tty())
    debug_log.debug_mode = "debug" in parsed.opts
    cmd.verbose_mode = "verbose" in parsed.opts


def launch(orig_args: List[str]) -> None:
    try:
        launch_internal(orig_args)
    except InteractionStopped:
        pass


def launch_internal(orig_args: List[str]) -> None:
    initial_current_directory: Optional[AbsPath] = get_current_directory_or_none()

    try:
        cli_opts = git_machete.options.CommandLineOptions()

        # Reset markup globals to the `--color=auto` baseline before parsing.
        # Two reasons: (1) `parse_cmdline` may raise a `MacheteException`, whose message is rendered at `__init__`
        # against the *current* `markup.use_ansi_escapes_in_stdout` - without a reset, a stale value from a prior invocation
        # (most relevant in the test harness, where one Python process runs many `cli.launch` calls back-to-back) would leak in.
        # (2) It keeps `parse_cmdline` itself side-effect-free; the actual `--color` override is applied below in `set_utils_global_variables`.
        markup.use_ansi_escapes_in_stdout = terminal.is_stdout_a_tty()
        markup.use_ansi_escapes_in_stderr = terminal.is_stderr_a_tty()

        parsed = parse_cmdline(orig_args)

        # Set up `--debug` / `--verbose` (and refine `--color` against the parsed value) before any subsequent `git config` read.
        set_utils_global_variables(parsed)

        if "help" in parsed.opts:
            print_fmt(get_help_description(display_help_topics=True, command=parsed.command))
            sys.exit(ExitCode.SUCCESS)
        if "version" in parsed.opts:
            version()
            return

        cmd = parsed.command
        if not cmd:
            print_fmt(get_help_description(display_help_topics=False))
            sys.exit(ExitCode.ARGUMENT_ERROR)

        if cmd not in ("d", "diff", "l", "log") and parsed.pass_through:
            print_fmt("Extra arguments after `--` are only allowed after `diff` and `log`")
            sys.exit(ExitCode.ARGUMENT_ERROR)

        # `completion`, `help` and `version` don't use `cli_opts`, so skip the CLI-options population for them.
        # Config keys that back tri-state options (`machete.traverse.push`, `machete.squashMergeDetection`) are read on demand
        # in the client method that actually needs them, so a malformed value never blows up unrelated commands like `help` or `add`.
        if cmd not in ("completion", "help", "version"):
            _populate_cli_options(cli_opts, parsed)

        if cmd == "add":
            add_client = MacheteClient()
            add_client.add(
                opt_branch=cli_opts.opt_branch,
                opt_onto=cli_opts.opt_onto,
                opt_as_first_child=cli_opts.opt_as_first_child,
                opt_as_root=cli_opts.opt_as_root,
                opt_yes=cli_opts.opt_yes,
                verbose=True,
                switch_head_if_new_branch=True)
        elif cmd == "advance":
            advance_client = AdvanceMacheteClient()
            advance_client.advance(opt_yes=cli_opts.opt_yes)
        elif cmd == "anno":
            spec = GITHUB_API_SPEC if cli_opts.opt_sync_github_prs else GITLAB_API_SPEC
            anno_client = AnnoMacheteClient(spec, verify_branches=False)
            annotation_text: List[str] = parsed.positionals.get("annotation_text", [])
            if cli_opts.opt_sync_github_prs or cli_opts.opt_sync_gitlab_mrs:
                anno_client.sync_annotations_to_prs(include_urls=False)
            elif annotation_text:
                anno_client.annotate(opt_branch=cli_opts.opt_branch, words=annotation_text)
            else:
                anno_client.print_annotation(opt_branch=cli_opts.opt_branch)
        elif cmd == "clean":
            clean_client = MacheteClientWithCodeHosting(GITHUB_API_SPEC)
            if "checkout-my-github-prs" in parsed.opts:
                clean_client.checkout_pull_requests(pr_numbers=[], mine=True)
            clean_client.delete_unmanaged(opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=cli_opts.opt_yes)
            clean_client.delete_untracked(opt_yes=cli_opts.opt_yes)
        elif cmd == "completion":
            completion_shell = parsed.positionals["shell"]

            def print_completion_resource(name: str) -> None:
                data = pkgutil.get_data("completion", name)
                if not data:
                    raise UnexpectedMacheteException(f"Completion file `{name}` not found.")
                print(data.decode())

            # Deliberately using if/else rather than a dict to measure coverage more accurately.
            if completion_shell == "bash":
                print_completion_resource("git-machete.completion.bash")
            elif completion_shell == "fish":
                print_completion_resource("git-machete.fish")
            elif completion_shell == "zsh":
                print_completion_resource("git-machete.completion.zsh")
            else:  # the parser already restricts the choices
                raise UnexpectedMacheteException(f"Unknown shell: `{completion_shell}`")
        elif cmd == "delete-unmanaged":
            delete_unmanaged_client = MacheteClient()
            delete_unmanaged_client.delete_unmanaged(
                opt_squash_merge_detection=cli_opts.opt_squash_merge_detection,
                opt_yes=cli_opts.opt_yes)
        elif cmd in {"diff", alias_by_command["diff"]}:
            diff_client = DiffMacheteClient()
            diff_client.display_diff(branch=cli_opts.opt_branch, opt_stat=cli_opts.opt_stat, extra_git_diff_args=parsed.pass_through)
        elif cmd == "discover":
            discover_client = DiscoverMacheteClient()
            discover_client.discover(
                opt_checked_out_since=cli_opts.opt_checked_out_since,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_roots=cli_opts.opt_roots,
                opt_yes=cli_opts.opt_yes)
        elif cmd in {"edit", alias_by_command["edit"]}:
            MacheteClient(read_layout_file=False).edit()
        elif cmd == "file":
            print(MacheteClient(read_layout_file=False).branch_layout_file_path)
        elif cmd == "fork-point":
            fork_point_client = ForkPointMacheteClient()

            if cli_opts.opt_inferred:
                fork_point_client.print_fork_point(
                    opt_branch=cli_opts.opt_branch, use_overrides=False, explain=cli_opts.opt_explain)
            elif cli_opts.opt_override_to:
                fork_point_client.override_fork_point_to(
                    opt_branch=cli_opts.opt_branch,
                    to_revision=AnyRevision.of(cli_opts.opt_override_to),
                    deprecated_flag_label="--override-to=...",
                    revision_label="selected commit")
            elif cli_opts.opt_override_to_inferred:
                fork_point_client.override_fork_point_to_inferred(opt_branch=cli_opts.opt_branch)
            elif cli_opts.opt_override_to_parent:
                fork_point_client.override_fork_point_to_parent(opt_branch=cli_opts.opt_branch)
            elif cli_opts.opt_unset_override:
                fork_point_client.unset_fork_point_override(opt_branch=cli_opts.opt_branch)
            else:
                fork_point_client.print_fork_point(
                    opt_branch=cli_opts.opt_branch, use_overrides=True, explain=cli_opts.opt_explain)
        elif cmd in {"github", "gitlab"}:
            subcommand = parsed.positionals[f"{cmd}_subcommand"]
            spec = GITHUB_API_SPEC if cmd == "github" else GITLAB_API_SPEC
            pr_or_mr = spec.pr_short_name.lower()
            request_ids: List[int] = parsed.positionals.get("request_id", [])
            # Each option's compatibility with each subcommand is encoded in the github/gitlab `CommandSpec`'s `subcommands` tuple
            # (see `cli_commands.py::_code_hosting_spec`), so the parser has already rejected the invalid combinations -
            # the dispatcher just runs the subcommand.

            github_or_gitlab_client = MacheteClientWithCodeHosting(spec)

            if subcommand == f"anno-{pr_or_mr}s":
                github_or_gitlab_client.sync_annotations_to_prs(include_urls=cli_opts.opt_with_urls)
            elif subcommand == f"checkout-{pr_or_mr}s":
                selectors_present = {
                    key for key in ("all", "by", "mine")
                    if key in parsed.opts
                }
                if request_ids:
                    selectors_present.add("request_id")
                if len(selectors_present) != 1:
                    raise MacheteException(
                        f"`checkout-{pr_or_mr}s` subcommand must take exactly one of the following options: "
                        f'`--all`, `--by=...`, `--mine`, `{pr_or_mr}-number(s)`')
                github_or_gitlab_client.checkout_pull_requests(
                    pr_numbers=request_ids,
                    all=cli_opts.opt_all,
                    mine=cli_opts.opt_mine,
                    by=cli_opts.opt_by,
                    fail_on_missing_current_user_for_my_open_prs=True)
            elif subcommand == f"create-{pr_or_mr}":
                github_or_gitlab_client.sync_before_creating_pull_request(opt_yes=cli_opts.opt_yes)
                github_or_gitlab_client.create_pull_request(
                    opt_base=cli_opts.opt_base,
                    opt_draft=cli_opts.opt_draft,
                    opt_title=cli_opts.opt_title,
                    opt_update_related_descriptions=cli_opts.opt_update_related_descriptions,
                    opt_yes=cli_opts.opt_yes)
            elif subcommand == f"restack-{pr_or_mr}":
                github_or_gitlab_client.restack_pull_request(opt_update_related_descriptions=cli_opts.opt_update_related_descriptions)
            elif subcommand == f"retarget-{pr_or_mr}":
                github_or_gitlab_client.retarget_pull_request(
                    opt_branch=cli_opts.opt_branch,
                    opt_ignore_if_missing=cli_opts.opt_ignore_if_missing,
                    opt_update_related_descriptions=cli_opts.opt_update_related_descriptions
                )
            elif subcommand == "sync":  # GitHub only
                github_or_gitlab_client.checkout_pull_requests(pr_numbers=[], mine=True)
                github_or_gitlab_client.delete_unmanaged(opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=False)
                github_or_gitlab_client.delete_untracked(opt_yes=cli_opts.opt_yes)
            elif subcommand == f"update-{pr_or_mr}-descriptions":
                selectors = {key for key in ("all", "by", "mine", "related") if key in parsed.opts}
                if len(selectors) > 1:
                    raise MacheteException(
                        f"`update-{pr_or_mr}-descriptions` subcommand takes at most one of the following options: "
                        '`--all`, `--by=...`, `--mine`, `--related`; '
                        '`--related` is assumed if none of these is provided.')
                related = cli_opts.opt_related or not selectors
                github_or_gitlab_client.update_pull_request_descriptions(
                    all=cli_opts.opt_all, by=cli_opts.opt_by, mine=cli_opts.opt_mine, related=related)
            else:  # an unknown subcommand is rejected by the parser
                raise UnexpectedMacheteException(f"Unknown subcommand: `{subcommand}`")
        elif cmd in {"go", alias_by_command["go"]}:
            direction: Optional[str] = parsed.positionals.get("direction")
            if direction is not None:
                GoShowMacheteClient().go(direction)
            else:
                GoInteractiveMacheteClient().go_interactive()
        elif cmd == "help":
            print_fmt(get_help_description(display_help_topics=True, command=parsed.positionals.get("topic_or_cmd")))
        elif cmd == "is-managed":
            if not MacheteClient().is_managed(opt_branch=cli_opts.opt_branch):
                sys.exit(ExitCode.MACHETE_EXCEPTION)
        elif cmd == "list":
            category = parsed.positionals["category"]
            list_branch: Optional[str] = parsed.positionals.get("branch")
            if category == "slidable-after" and not list_branch:
                raise MacheteException(f"`git machete list {category}` requires an extra <branch> argument")
            elif category != "slidable-after" and list_branch:
                raise MacheteException(f"`git machete list {category}` does not expect extra arguments")

            list_client = ListMacheteClient()
            res: Sequence[LocalBranchShortName] = []
            if category == "addable":
                res = list_client.addable_branches()
            elif category == "childless":
                res = list_client.childless_managed_branches()
            elif category == "managed":
                res = list_client.managed_branches
            elif category == "slidable":
                res = list_client.slidable_branches()
            elif category == "slidable-after":
                # `list_branch` is non-None here:
                # the early-exit check above raised when `category == 'slidable-after' and not list_branch`.
                assert list_branch is not None
                target_branch = LocalBranchShortName.of(list_branch)
                list_client.expect_in_managed_branches(target_branch)
                res = list_client.get_slidable_after(target_branch)
            elif category == "unmanaged":
                res = list_client.unmanaged_branches()
            elif category == "with-overridden-fork-point":
                res = list_client.branches_with_overridden_fork_point()
            else:  # rejected by the parser
                raise UnexpectedMacheteException(f"Invalid category: `{category}`")

            if res:
                print("\n".join(res))
        elif cmd in {"log", alias_by_command["log"]}:
            LogMacheteClient().display_log(opt_branch=cli_opts.opt_branch, extra_git_log_args=parsed.pass_through)
        elif cmd == "reapply":
            ReapplyMacheteClient().reapply(
                opt_fork_point=cli_opts.opt_fork_point,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase)
        elif cmd == "rename":
            RenameMacheteClient().rename(
                opt_branch=cli_opts.opt_branch,
                new_name=LocalBranchShortName.of(parsed.positionals["new_name"]),
                opt_repoint_tracking=cli_opts.opt_repoint_tracking)
        elif cmd == "show":
            show_direction = parsed.positionals["direction"]
            if show_direction == "current" and cli_opts.opt_branch:
                raise MacheteException('`show current` with a `<branch>` argument does not make sense')
            GoShowMacheteClient(verify_branches=False).show(show_direction, opt_branch=cli_opts.opt_branch)
        elif cmd == "slide-out":
            # `verify_branches=False` so that a branch the user is *explicitly* asking to slide out
            # doesn't first trigger the "Warning: sliding invalid branch ..." auto-prune
            # (which then makes the explicit slide-out fail with "not found in the tree of branch dependencies").
            # The auto-prune is useful for commands that just *read* the layout (e.g. `status`, `traverse`);
            # for `slide-out` it's redundant with the user's own intent.
            slide_out_client = SlideOutMacheteClient(verify_branches=False)
            branches_to_slide_out: List[str] = parsed.positionals.get("branches", [])
            if cli_opts.opt_removed_from_remote:
                if (branches_to_slide_out or cli_opts.opt_down_fork_point or cli_opts.opt_merge or
                        cli_opts.opt_no_interactive_rebase or cli_opts.opt_no_rebase):
                    raise MacheteException("Only `--delete` can be passed with `--removed-from-remote`")
                slide_out_client.slide_out_removed_from_remote(opt_delete=cli_opts.opt_delete)
            else:
                slide_out_client.slide_out(
                    opt_branches=([LocalBranchShortName.of(branch) for branch in branches_to_slide_out]
                                  if branches_to_slide_out else None),
                    opt_delete=cli_opts.opt_delete,
                    opt_down_fork_point=cli_opts.opt_down_fork_point,
                    opt_merge=cli_opts.opt_merge,
                    opt_no_edit_merge=cli_opts.opt_no_edit_merge,
                    opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                    opt_no_rebase=cli_opts.opt_no_rebase)
        elif cmd == "squash":
            SquashMacheteClient().squash(opt_fork_point=cli_opts.opt_fork_point)
        elif cmd in {"status", alias_by_command["status"]}:
            status_client = StatusMacheteClient(
                interactively_slide_out_invalid_branches=terminal.is_stdout_a_tty())
            status_client.expect_at_least_one_managed_branch()
            status_client.status(
                warn_when_branch_in_sync_but_fork_point_off=True,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_list_commits_with_hashes=cli_opts.opt_list_commits_with_hashes,
                opt_squash_merge_detection=cli_opts.opt_squash_merge_detection)
        elif cmd in {"traverse", alias_by_command["traverse"]}:
            opt_return_to = TraverseReturnTo.from_string(cli_opts.opt_return_to, "`--return-to` flag")

            spec = GITHUB_API_SPEC if cli_opts.opt_sync_github_prs else GITLAB_API_SPEC
            traverse_client = TraverseMacheteClient(
                spec, interactively_slide_out_invalid_branches=terminal.is_stdout_a_tty())
            traverse_client.traverse(
                opt_fetch=cli_opts.opt_fetch,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_merge=cli_opts.opt_merge,
                opt_no_edit_merge=cli_opts.opt_no_edit_merge,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                opt_push_tracked=cli_opts.opt_push_tracked,
                opt_push_untracked=cli_opts.opt_push_untracked,
                opt_return_to=opt_return_to,
                opt_squash_merge_detection=cli_opts.opt_squash_merge_detection,
                opt_start_from=cli_opts.opt_start_from,
                opt_stop_after=cli_opts.opt_stop_after,
                opt_sync_github_prs=cli_opts.opt_sync_github_prs,
                opt_sync_gitlab_mrs=cli_opts.opt_sync_gitlab_mrs,
                opt_yes=cli_opts.opt_yes)
        elif cmd == "update":
            UpdateMacheteClient().update(
                opt_merge=cli_opts.opt_merge,
                opt_no_edit_merge=cli_opts.opt_no_edit_merge,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                opt_fork_point=cli_opts.opt_fork_point)
        elif cmd == "version":
            version()
        else:  # rejected by the parser
            raise UnexpectedMacheteException(f"Unknown command: `{cmd}`")
    finally:
        # Has been fixed in git itself as of 2.35.0, but we still defend against pre-2.35 + the underlying-checkout-moves-cwd case:
        # see https://github.com/git/git/blob/master/Documentation/RelNotes/2.35.0.txt#L81
        if initial_current_directory and not does_directory_exist(initial_current_directory):
            nearest_existing_parent_directory: AbsPath = initial_current_directory
            while not does_directory_exist(nearest_existing_parent_directory):
                nearest_existing_parent_directory = nearest_existing_parent_directory.parent_dir()
            warn(f"current directory {initial_current_directory} no longer exists, "
                 f"the nearest existing parent directory is {nearest_existing_parent_directory}")


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
