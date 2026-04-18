#!/usr/bin/env python3

import argparse
import itertools
import os
import pkgutil
import sys
import textwrap
from typing import (Any, Dict, Iterable, List, NoReturn, Optional, Sequence,
                    Tuple, TypeVar, Union)

import git_machete.options
from git_machete import __version__, dispatch, utils
from git_machete.config import MacheteConfig, SquashMergeDetection
from git_machete.github import GITHUB_CLIENT_SPEC
from git_machete.gitlab import GITLAB_CLIENT_SPEC

from .generated_docs import long_docs, short_docs
from .git_operations import AnyRevision, GitContext, LocalBranchShortName
from .utils import (ExitCode, InteractionStopped, MacheteException,
                    UnderlyingGitException, UnexpectedMacheteException,
                    print_fmt, warn)

T = TypeVar('T')

alias_by_command: Dict[str, str] = {
    "diff": "d",
    "edit": "e",
    "go": "g",
    "log": "l",
    "status": "s",
    "traverse": "t"
}

command_by_alias: Dict[str, str] = {v: k for k, v in alias_by_command.items()}

command_groups: List[Tuple[str, List[str]]] = [
    ("General topics",
     ["completion", "config", "file", "format", "help", "hooks", "version"]),
    ("Build, display and modify the tree of branch dependencies",
     ["add", "anno", "discover", "edit", "status"]),
    ("List, check out and delete branches",
     ["delete-unmanaged", "go", "is-managed", "list", "show"]),
    ("Determine changes specific to the given branch",
     ["diff", "fork-point", "log"]),
    ("Update git history in accordance with the tree of branch dependencies",
     ["advance", "reapply", "slide-out", "squash", "traverse", "update"]),
    ("Integrate with third party tools",
     ["github", "gitlab"])
]

commands_and_aliases = list(long_docs.keys()) + list(command_by_alias.keys())


def get_help_description(*, display_help_topics: bool, command: Optional[str] = None) -> str:
    """Return a help/usage string in markup (to be resolved by `print_fmt`)."""
    usage_str = ''
    if command in long_docs:
        usage_str += textwrap.dedent(long_docs[command])
    elif command in command_by_alias:
        usage_str += textwrap.dedent(long_docs[command_by_alias[command]])
    else:
        usage_str += get_short_general_usage() + '\n'
        usage_str += ("\n<u>Quick start tip</u>\n\n"
                      "    Get familiar with the help for <b>format</b>, <b>edit</b>,"
                      " <b>status</b> and <b>update</b>, in this order.\n\n")
        for hdr, cmds in command_groups:
            if not display_help_topics:
                if hdr == 'General topics':
                    cmds = [topic for topic in cmds if topic not in ['config', 'format', 'hooks']]
            usage_str += f'<u>{hdr}</u>\n\n'
            for cm in cmds:
                alias = f", {alias_by_command[cm]}" if cm in alias_by_command else ""
                label = cm + alias
                usage_str += f'    <b>{label}</b>{" " * max(0, 18 - len(label))}{short_docs[cm]}\n'
            usage_str += '\n'
        usage_str += textwrap.dedent("""
            <u>General options</u>\n
                <b>--debug</b>           Log detailed diagnostic info, including outputs of the executed git commands.
                <b>-h, --help</b>        Print help and exit.
                <b>-v, --verbose</b>     Log the executed git commands.
                <b>--version</b>         Print version and exit.
        """[1:])
    return usage_str


def get_short_general_usage() -> str:
    return ("<b>Usage: git machete [--debug] [-h] [-v|--verbose] [--version] "
            "<command> [command-specific options] [command-specific argument]</b>")


def version() -> None:
    print(f"git-machete version {__version__}")


class MacheteHelpAction(argparse.Action):
    def __init__(  # noqa: KW101
            self,
            option_strings: str,
            dest: str = argparse.SUPPRESS,
            default: Any = argparse.SUPPRESS,
            help: Optional[str] = None
    ) -> None:
        super(MacheteHelpAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)

    def __call__(  # noqa: KW101
            self,
            parser: argparse.ArgumentParser,
            namespace: argparse.Namespace,  # noqa: F841, U100
            values: Union[str, Sequence[Any], None],  # noqa: U100
            option_string: Optional[str] = None  # noqa: F841, U100
    ) -> None:
        # parser name (prog) is expected to be `git machete` or `git machete <command>`
        command_name = parser.prog.replace('git machete', '').strip()
        print_fmt(get_help_description(display_help_topics=True, command=command_name))
        parser.exit(status=ExitCode.SUCCESS)


def create_cli_parser() -> argparse.ArgumentParser:
    common_args_parser = argparse.ArgumentParser(
        prog='git machete',
        argument_default=argparse.SUPPRESS,
        add_help=False)
    common_args_parser.add_argument('--debug', action='store_true')
    common_args_parser.add_argument('-h', '--help', action=MacheteHelpAction)
    common_args_parser.add_argument('--version', action='version', version=f'git-machete version {__version__}')
    common_args_parser.add_argument('-v', '--verbose', action='store_true')

    class CustomArgumentParser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            if "the following arguments are required: github subcommand" in message:
                print(f"{message.replace(', request_id', '')}\nPossible values for subcommand are: "
                      "anno-prs, checkout-prs, create-pr, restack-pr, retarget-pr, update-pr-descriptions, sync", file=sys.stderr)
                self.exit(2)
            elif "the following arguments are required: gitlab subcommand" in message:
                print(f"{message.replace(', request_id', '')}\nPossible values for subcommand are: "
                      "anno-mrs, checkout-mrs, create-mr, restack-mr, retarget-mr, update-mr-descriptions", file=sys.stderr)
                self.exit(2)
            elif "the following arguments are required: show direction" in message:
                print(f"{message}\nPossible values for show direction are: "
                      f"c, current, d, down, f, first, l, last, n, next, p, prev, r, root, u, up", file=sys.stderr)
                self.exit(2)
            else:
                super().error(message)

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
    fork_point_exclusive_optional_args = fork_point_parser.add_mutually_exclusive_group()
    fork_point_exclusive_optional_args.add_argument('--inferred', action='store_true')
    fork_point_exclusive_optional_args.add_argument('--override-to')
    fork_point_exclusive_optional_args.add_argument('--override-to-inferred', action='store_true')
    fork_point_exclusive_optional_args.add_argument('--override-to-parent', action='store_true')
    fork_point_exclusive_optional_args.add_argument('--unset-override', action='store_true')

    def add_code_hosting_parser(command: str, pr_or_mr: str, include_sync: bool) -> Any:
        parser = create_subparser(command)
        parser.add_argument('subcommand', metavar=f'{command} subcommand', choices=[
            f'anno-{pr_or_mr}s',
            f'checkout-{pr_or_mr}s',
            f'create-{pr_or_mr}',
            f'restack-{pr_or_mr}',
            f'retarget-{pr_or_mr}',
            f'update-{pr_or_mr}-descriptions'
        ] + (['sync'] if include_sync else []))
        parser.add_argument('request_id', nargs='*', type=int)
        parser.add_argument('-b', '--branch')
        parser.add_argument('--all', action='store_true')
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
            warn("`--no-detect-squash-merges` is deprecated, use `--squash-merge-detection=none` instead",
                 extra_newline=True)
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
        git: GitContext
) -> None:
    traverse_push = MacheteConfig(git).traverse_push()
    if traverse_push is not None:
        cli_opts.opt_push_tracked = cli_opts.opt_push_untracked = traverse_push


def set_utils_global_variables(parsed_args: argparse.Namespace) -> None:
    args = vars(parsed_args)
    color = args.get("color")
    utils.use_ansi_escapes_in_stdout = color == "always" or (color in {None, "auto"} and utils.is_stdout_a_tty())
    utils.use_ansi_escapes_in_stderr = color == "always" or (color in {None, "auto"} and utils.is_stderr_a_tty())
    utils.debug_mode = "debug" in args
    utils.verbose_mode = "verbose" in args


def launch(orig_args: List[str]) -> None:
    try:
        launch_internal(orig_args)
    except InteractionStopped:
        pass


def launch_internal(orig_args: List[str]) -> None:
    initial_current_directory: Optional[str] = utils.get_current_directory_or_none()

    try:
        cli_opts = git_machete.options.CommandLineOptions()
        git = GitContext()

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

        if cmd == "add":
            if cli_opts.opt_as_root and cli_opts.opt_onto:
                raise MacheteException("Option `-R/--as-root` cannot be specified together with `-o/--onto`.")
            if cli_opts.opt_as_root and cli_opts.opt_as_first_child:
                raise MacheteException("Option `-R/--as-root` cannot be specified together with `-f/--as-first-child`.")
            dispatch.add(
                git,
                branch=cli_opts.opt_branch or git.get_current_branch(),
                opt_onto=cli_opts.opt_onto,
                opt_as_first_child=cli_opts.opt_as_first_child,
                opt_as_root=cli_opts.opt_as_root,
                opt_yes=cli_opts.opt_yes)
        elif cmd == "advance":
            dispatch.advance(git, opt_yes=cli_opts.opt_yes)
        elif cmd == "anno":
            spec = GITHUB_CLIENT_SPEC if cli_opts.opt_sync_github_prs else GITLAB_CLIENT_SPEC
            dispatch.anno(
                git,
                branch=cli_opts.opt_branch or git.get_current_branch(),
                annotation_text=parsed_cli.annotation_text if 'annotation_text' in parsed_cli else None,
                opt_sync_github_prs=cli_opts.opt_sync_github_prs,
                opt_sync_gitlab_mrs=cli_opts.opt_sync_gitlab_mrs,
                spec=spec)
        elif cmd == "clean":
            dispatch.clean(
                git,
                opt_checkout_my_github_prs='checkout_my_github_prs' in parsed_cli,
                opt_yes=cli_opts.opt_yes,
                spec=GITHUB_CLIENT_SPEC)
        elif cmd == "completion":
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

        elif cmd == "delete-unmanaged":
            dispatch.delete_unmanaged(git, opt_yes=cli_opts.opt_yes)
        elif cmd in {"diff", alias_by_command["diff"]}:
            dispatch.diff(
                git,
                branch=cli_opts.opt_branch,
                opt_stat=cli_opts.opt_stat,
                extra_args=pass_through_args)
        elif cmd == "discover":
            dispatch.discover(
                git,
                opt_checked_out_since=cli_opts.opt_checked_out_since,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_roots=cli_opts.opt_roots,
                opt_yes=cli_opts.opt_yes)
        elif cmd in {"edit", alias_by_command["edit"]}:
            dispatch.edit(git)
        elif cmd == "file":
            dispatch.file(git)
        elif cmd == "fork-point":
            dispatch.fork_point(
                git,
                branch=cli_opts.opt_branch or git.get_current_branch(),
                opt_inferred=cli_opts.opt_inferred,
                opt_override_to=cli_opts.opt_override_to,
                opt_override_to_inferred=cli_opts.opt_override_to_inferred,
                opt_override_to_parent=cli_opts.opt_override_to_parent,
                opt_unset_override=cli_opts.opt_unset_override)
        elif cmd in {"github", "gitlab"}:
            subcommand = parsed_cli.subcommand
            spec = GITHUB_CLIENT_SPEC if cmd == "github" else GITLAB_CLIENT_SPEC
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

            if subcommand == f"anno-{pr_or_mr}s":
                dispatch.code_hosting_anno_prs(git, spec, include_urls=cli_opts.opt_with_urls)
            elif subcommand == f"checkout-{pr_or_mr}s":
                if len(set(parsed_cli_as_dict.keys()).intersection({'all', 'by', 'mine', 'request_id'})) != 1:
                    raise MacheteException(
                        f"`checkout-{pr_or_mr}s` subcommand must take exactly one of the following options: "
                        f'`--all`, `--by=...`, `--mine`, `{pr_or_mr}-number(s)`')
                dispatch.code_hosting_checkout_prs(
                    git, spec,
                    pr_numbers=parsed_cli.request_id if 'request_id' in parsed_cli else [],
                    opt_all=cli_opts.opt_all,
                    opt_mine=cli_opts.opt_mine,
                    opt_by=cli_opts.opt_by)
            elif subcommand == f"create-{pr_or_mr}":
                dispatch.code_hosting_create_pr(
                    git, spec,
                    opt_base=cli_opts.opt_base,
                    opt_draft=cli_opts.opt_draft,
                    opt_title=cli_opts.opt_title,
                    opt_update_related_descriptions=cli_opts.opt_update_related_descriptions,
                    opt_yes=cli_opts.opt_yes)
            elif subcommand == f"restack-{pr_or_mr}":
                dispatch.code_hosting_restack_pr(git, spec,
                                                 opt_update_related_descriptions=cli_opts.opt_update_related_descriptions)
            elif subcommand == f"retarget-{pr_or_mr}":
                dispatch.code_hosting_retarget_pr(
                    git, spec,
                    branch=cli_opts.opt_branch or git.get_current_branch(),
                    opt_ignore_if_missing=cli_opts.opt_ignore_if_missing,
                    opt_update_related_descriptions=cli_opts.opt_update_related_descriptions)
            elif subcommand == "sync":  # GitHub only
                dispatch.code_hosting_sync(git, spec, opt_yes=cli_opts.opt_yes)
            elif subcommand == f"update-{pr_or_mr}-descriptions":
                if len(set(parsed_cli_as_dict.keys()).intersection({'all', 'by', 'mine', 'related'})) != 1:
                    raise MacheteException(
                        f"`update-{pr_or_mr}-descriptions` subcommand must take exactly one of the following options: "
                        '`--all`, `--by=...`, `--mine`, `--related`')
                dispatch.code_hosting_update_pr_descriptions(
                    git, spec,
                    opt_all=cli_opts.opt_all,
                    opt_by=cli_opts.opt_by,
                    opt_mine=cli_opts.opt_mine,
                    opt_related=cli_opts.opt_related)
            else:  # an unknown subcommand is handled by argparse
                raise UnexpectedMacheteException(f"Unknown subcommand: `{subcommand}`")
        elif cmd in {"go", alias_by_command["go"]}:
            dispatch.go(git, direction=parsed_cli.direction)
        elif cmd == "is-managed":
            branch = cli_opts.opt_branch or git.get_current_branch()
            if not dispatch.is_managed(git, branch=branch):
                sys.exit(ExitCode.MACHETE_EXCEPTION)
        elif cmd == "list":
            category = parsed_cli.category
            if category == 'slidable-after' and not cli_opts.opt_branch:
                raise MacheteException(f"`git machete list {category}` requires an extra <branch> argument")
            elif category != 'slidable-after' and cli_opts.opt_branch:
                raise MacheteException(f"`git machete list {category}` does not expect extra arguments")
            dispatch.list_branches(git, category=category, branch=cli_opts.opt_branch)
        elif cmd in {"log", alias_by_command["log"]}:
            dispatch.log(
                git,
                branch=cli_opts.opt_branch or git.get_current_branch(),
                extra_args=pass_through_args)
        elif cmd == "reapply":
            dispatch.reapply(
                git,
                opt_fork_point=cli_opts.opt_fork_point,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase)
        elif cmd == "show":
            direction = parsed_cli.direction
            if direction == "current" and cli_opts.opt_branch:
                raise MacheteException('`show current` with a `<branch>` argument does not make sense')
            dispatch.show(
                git,
                direction=direction,
                branch=cli_opts.opt_branch or git.get_current_branch())
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

            branches_to_slide_out: Optional[List[str]] = parsed_cli_as_dict.get('branches')
            if cli_opts.opt_removed_from_remote:
                if (branches_to_slide_out or cli_opts.opt_down_fork_point or cli_opts.opt_merge or
                        cli_opts.opt_no_interactive_rebase or cli_opts.opt_no_rebase):
                    raise MacheteException("Only `--delete` can be passed with `--removed-from-remote`")

            dispatch.slide_out(
                git,
                branches=[LocalBranchShortName.of(branch)
                          for branch in (branches_to_slide_out or [git.get_current_branch()])],
                opt_delete=cli_opts.opt_delete,
                opt_down_fork_point=cli_opts.opt_down_fork_point,
                opt_merge=cli_opts.opt_merge,
                opt_no_edit_merge=cli_opts.opt_no_edit_merge,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                opt_no_rebase=cli_opts.opt_no_rebase,
                opt_removed_from_remote=cli_opts.opt_removed_from_remote)
        elif cmd == "squash":
            dispatch.squash(git, opt_fork_point=cli_opts.opt_fork_point)
        elif cmd in {"status", alias_by_command["status"]}:
            dispatch.status(
                git,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_list_commits_with_hashes=cli_opts.opt_list_commits_with_hashes,
                opt_squash_merge_detection=squash_merge_detection())
        elif cmd in {"traverse", alias_by_command["traverse"]}:
            spec = GITHUB_CLIENT_SPEC if cli_opts.opt_sync_github_prs else GITLAB_CLIENT_SPEC
            dispatch.traverse(
                git,
                opt_fetch=cli_opts.opt_fetch,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_merge=cli_opts.opt_merge,
                opt_no_edit_merge=cli_opts.opt_no_edit_merge,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                opt_push_tracked=cli_opts.opt_push_tracked,
                opt_push_untracked=cli_opts.opt_push_untracked,
                opt_return_to=cli_opts.opt_return_to,
                opt_squash_merge_detection=squash_merge_detection(),
                opt_start_from=cli_opts.opt_start_from,
                opt_stop_after=cli_opts.opt_stop_after,
                opt_sync_github_prs=cli_opts.opt_sync_github_prs,
                opt_sync_gitlab_mrs=cli_opts.opt_sync_gitlab_mrs,
                opt_yes=cli_opts.opt_yes,
                spec=spec)
        elif cmd == "update":
            dispatch.update(
                git,
                opt_merge=cli_opts.opt_merge,
                opt_no_edit_merge=cli_opts.opt_no_edit_merge,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                opt_fork_point=cli_opts.opt_fork_point)
        elif cmd == "version":
            version()
        else:  # an unknown command is handled by argparse
            raise UnexpectedMacheteException(f"Unknown command: `{cmd}`")
    finally:
        # Note that this problem (current directory no longer existing due to e.g. underlying git checkouts)
        # has been fixed in git itself as of 2.35.0:
        # see https://github.com/git/git/blob/master/Documentation/RelNotes/2.35.0.txt#L81
        if initial_current_directory and not utils.does_directory_exist(initial_current_directory):
            nearest_existing_parent_directory = initial_current_directory
            while not utils.does_directory_exist(nearest_existing_parent_directory):
                nearest_existing_parent_directory = utils.join_paths_posix(
                    nearest_existing_parent_directory, os.path.pardir)
            warn(f"current directory {initial_current_directory} no longer exists, "
                 f"the nearest existing parent directory is {utils.abspath_posix(nearest_existing_parent_directory)}")


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
