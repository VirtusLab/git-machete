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
from git_machete import __version__, git_config_keys, utils
from git_machete.client.advance import AdvanceMacheteClient
from git_machete.client.anno import AnnoMacheteClient
from git_machete.client.base import (MacheteClient, SquashMergeDetection,
                                     TraverseReturnTo, TraverseStartFrom)
from git_machete.client.diff import DiffMacheteClient
from git_machete.client.discover import DiscoverMacheteClient
from git_machete.client.fork_point import ForkPointMacheteClient
from git_machete.client.go_show import GoShowMacheteClient
from git_machete.client.log import LogMacheteClient
from git_machete.client.slide_out import SlideOutMacheteClient
from git_machete.client.squash import SquashMacheteClient
from git_machete.client.traverse import TraverseMacheteClient
from git_machete.client.update import UpdateMacheteClient
from git_machete.client.with_code_hosting import MacheteClientWithCodeHosting
from git_machete.github import GITHUB_CLIENT_SPEC
from git_machete.gitlab import GITLAB_CLIENT_SPEC

from .exceptions import (ExitCode, InteractionStopped, MacheteException,
                         UnderlyingGitException, UnexpectedMacheteException)
from .generated_docs import long_docs, short_docs
from .git_operations import AnyRevision, GitContext, LocalBranchShortName
from .utils import bold, fmt, underline, warn

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
    usage_str = ''
    if command in long_docs:
        usage_str += fmt(textwrap.dedent(long_docs[command]))
    elif command in command_by_alias:
        usage_str += fmt(textwrap.dedent(long_docs[command_by_alias[command]]))
    else:
        usage_str += get_short_general_usage() + '\n' + fmt(
            "\n<u>Quick start tip</u>\n\n"
            "    Get familiar with the help for <b>format</b>, <b>edit</b>,"
            " <b>status</b> and <b>update</b>, in this order.\n\n")
        for hdr, cmds in command_groups:
            if not display_help_topics:
                if hdr == 'General topics':
                    cmds = [topic for topic in cmds if topic not in ['config', 'format', 'hooks']]
            usage_str += underline(hdr) + '\n\n'
            for cm in cmds:
                alias = f", {alias_by_command[cm]}" if cm in alias_by_command else ""
                usage_str += f'    {bold(cm + alias): <{18 if utils.ascii_only else 27}}{short_docs[cm]}'
                usage_str += '\n'
            usage_str += '\n'
        usage_str += fmt(textwrap.dedent("""
            <u>General options</u>\n
                <b>--debug</b>           Log detailed diagnostic info, including outputs of the executed git commands.
                <b>-h, --help</b>        Print help and exit.
                <b>-v, --verbose</b>     Log the executed git commands.
                <b>--version</b>         Print version and exit.
        """[1:]))
    return usage_str


def get_short_general_usage() -> str:
    return (fmt("<b>Usage: git machete [--debug] [-h] [-v|--verbose] [--version] "
                "<command> [command-specific options] [command-specific argument]</b>"))


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
        print(get_help_description(display_help_topics=True, command=command_name))
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
            elif "the following arguments are required: go direction" in message:
                print(f"{message}\nPossible values for go direction are: "
                      f"d, down, f, first, l, last, n, next, p, prev, r, root, u, up", file=sys.stderr)
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
        parser.add_argument('--by')
        parser.add_argument('--draft', action='store_true')
        parser.add_argument('--ignore-if-missing', action='store_true')
        parser.add_argument('--mine', action='store_true')
        parser.add_argument('--related', action='store_true')
        parser.add_argument('--title')
        parser.add_argument('-U', '--update-related-descriptions', action='store_true')
        parser.add_argument('--with-urls', action='store_true')
        parser.add_argument('--yes', action='store_true')

    add_code_hosting_parser('github', 'pr', include_sync=True)
    add_code_hosting_parser('gitlab', 'mr', include_sync=False)

    go_parser = create_subparser('go', alias='g')
    go_parser.add_argument('direction', metavar='go direction', choices=[
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
            warn("`--no-detect-squash-merges` is deprecated, use `--squash-merge-detection=none` instead", end="\n\n")
            cli_opts.opt_squash_merge_detection_string = "none"
        elif opt == "no_edit_merge":
            cli_opts.opt_no_edit_merge = True
        elif opt == "no_interactive_rebase":
            cli_opts.opt_no_interactive_rebase = True
        elif opt == "no_push":
            cli_opts.opt_push_tracked = False
            cli_opts.opt_push_untracked = False
        elif opt == "no_push_untracked":
            cli_opts.opt_push_untracked = False
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
    machete_traverse_push_config_key = git.get_boolean_config_attr_or_none(key=git_config_keys.TRAVERSE_PUSH)
    if machete_traverse_push_config_key is not None:
        if machete_traverse_push_config_key:
            cli_opts.opt_push_tracked, cli_opts.opt_push_untracked = True, True
        else:
            cli_opts.opt_push_tracked, cli_opts.opt_push_untracked = False, False

    squash_merge_detection = git.get_config_attr_or_none(key=git_config_keys.SQUASH_MERGE_DETECTION)
    if squash_merge_detection is not None:
        # Let's defer the validation until the value is actually used in `status` or `traverse`.
        # Otherwise, if an invalid value ends up in git config, `git machete help` will instantly fail.
        cli_opts.opt_squash_merge_detection_string = squash_merge_detection
        cli_opts.opt_squash_merge_detection_origin = f"`{git_config_keys.SQUASH_MERGE_DETECTION}` git config key"


def set_utils_global_variables(parsed_args: argparse.Namespace) -> None:
    args = vars(parsed_args)
    utils.ascii_only = args.get("color") == "never" or (args.get("color") in {None, "auto"} and not sys.stdout.isatty())
    utils.debug_mode = "debug" in args
    utils.verbose_mode = "verbose" in args


def launch(orig_args: List[str]) -> None:
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
            print(get_help_description(display_help_topics=False))
            sys.exit(ExitCode.ARGUMENT_ERROR)

        if cmd not in ("d", "diff", "l", "log") and pass_through_args:
            print(fmt("Extra arguments after `--` are only allowed after `diff` and `log`"))
            sys.exit(ExitCode.ARGUMENT_ERROR)
        if pass_through_args and pass_through_args[0] == "--":
            pass_through_args = pass_through_args[1:]

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
            print(get_help_description(display_help_topics=True, command=parsed_cli.topic_or_cmd))
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
            spec = GITHUB_CLIENT_SPEC if cli_opts.opt_sync_github_prs else GITLAB_CLIENT_SPEC
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
            clean_client = MacheteClientWithCodeHosting(git, GITHUB_CLIENT_SPEC)
            clean_client.read_branch_layout_file()
            if 'checkout_my_github_prs' in parsed_cli:
                clean_client.checkout_pull_requests(pr_numbers=[], mine=True)
            clean_client.delete_unmanaged(opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=cli_opts.opt_yes)
            clean_client.delete_untracked(opt_yes=cli_opts.opt_yes)
        elif cmd == "delete-unmanaged":
            delete_unmanaged_client = MacheteClient(git)
            delete_unmanaged_client.read_branch_layout_file()
            opt_squash_merge_detection = SquashMergeDetection.from_string(
                cli_opts.opt_squash_merge_detection_string, cli_opts.opt_squash_merge_detection_origin)
            delete_unmanaged_client.delete_unmanaged(opt_squash_merge_detection=opt_squash_merge_detection, opt_yes=cli_opts.opt_yes)
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
            print(os.path.abspath(file_client.branch_layout_file_path))
        elif cmd == "fork-point":
            fork_point_client = ForkPointMacheteClient(git)
            fork_point_client.read_branch_layout_file()
            branch = cli_opts.opt_branch or git.get_current_branch()
            upstream = fork_point_client.up_branch_for(branch)
            fork_point_client.expect_in_local_branches(branch)

            def warn_on_deprecation(*, flag: str, revision: AnyRevision, revision_str: str) -> None:
                if upstream:
                    print()
                    warn(
                        f"`git machete fork-point {flag}` may lead to a confusing user experience and is deprecated.\n\n"
                        f"If the commits between <b>{upstream}</b> (parent of <b>{branch}</b>) "
                        f"and {revision_str} <b>{git.get_short_commit_hash_by_revision_or_none(revision) or ''}</b> "
                        f"do NOT belong to <b>{branch}</b>, consider using:\n"
                        f"    `git machete update --fork-point=\"{revision}\" {branch}`\n\n"
                        "Otherwise, if you're okay with treating these commits "
                        f"as a part of <b>{branch}</b>'s unique history, use instead:\n"
                        f"    `git machete fork-point --override-to-parent {branch}`"
                    )
                # It's unlikely that anyone overrides fork point for a branch that doesn't have a parent,
                # also it's unclear what the suggested action should even be - let's skip this case.

            if cli_opts.opt_inferred:
                print(fork_point_client.fork_point(branch=branch, use_overrides=False))
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
                if upstream:
                    fork_point_client.set_fork_point_override(branch, upstream)
                else:
                    raise MacheteException(
                        f"Branch {bold(branch)} does not have upstream (parent) branch")
            elif cli_opts.opt_unset_override:
                fork_point_client.unset_fork_point_override(branch)
            else:
                print(fork_point_client.fork_point(branch=branch, use_overrides=True))
        elif cmd in {"go", alias_by_command["go"]}:
            go_client = GoShowMacheteClient(git)
            go_client.read_branch_layout_file()
            git.expect_no_operation_in_progress()
            current_branch = git.get_current_branch()
            # with pick_if_multiple=True, there returned list will have exactly one element
            dest = go_client.parse_direction(parsed_cli.direction, branch=current_branch, allow_current=False, pick_if_multiple=True)[0]
            if dest != current_branch:
                git.checkout(dest)
        elif cmd in ("github", "gitlab"):
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
                try:
                    github_or_gitlab_client.sync_before_creating_pull_request(opt_yes=cli_opts.opt_yes)
                except InteractionStopped:
                    return
                github_or_gitlab_client.create_pull_request(
                    head=current_branch,
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
                if len(set(parsed_cli_as_dict.keys()).intersection({'all', 'by', 'mine', 'related'})) != 1:
                    raise MacheteException(
                        f"`update-{pr_or_mr}-descriptions` subcommand must take exactly one of the following options: "
                        '`--all`, `--by=...`, `--mine`, `--related`')
                github_or_gitlab_client.update_pull_request_descriptions(
                    all=cli_opts.opt_all, by=cli_opts.opt_by, mine=cli_opts.opt_mine, related=cli_opts.opt_related)
            else:  # an unknown subcommand is handled by argparse
                raise UnexpectedMacheteException(f"Unknown subcommand: `{subcommand}`")
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

            list_client = MacheteClient(git)
            list_client.read_branch_layout_file()
            res = []
            if category == "addable":
                res = list_client.addable_branches
            elif category == "childless":
                res = list_client.childless_managed_branches
            elif category == "managed":
                res = list_client.managed_branches
            elif category == "slidable":
                res = list_client.slidable_branches
            elif category == "slidable-after":
                list_client.expect_in_managed_branches(parsed_cli.branch)
                res = list_client.get_slidable_after(parsed_cli.branch)
            elif category == "unmanaged":
                res = list_client.unmanaged_branches
            elif category == "with-overridden-fork-point":
                res = list_client.branches_with_overridden_fork_point
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
            reapply_client = MacheteClient(git)
            reapply_client.read_branch_layout_file()
            current_branch = git.get_current_branch()
            if cli_opts.opt_fork_point is not None:
                reapply_client.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                    fork_point=cli_opts.opt_fork_point, branch=current_branch)

            reapply_fork_point = cli_opts.opt_fork_point or reapply_client.fork_point(branch=current_branch, use_overrides=True)
            reapply_client.rebase(
                onto=reapply_fork_point,
                from_exclusive=reapply_fork_point,
                branch=current_branch,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase)
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

            slide_out_client = SlideOutMacheteClient(git)
            slide_out_client.read_branch_layout_file()
            branches_to_slide_out: Optional[List[str]] = parsed_cli_as_dict.get('branches')
            if cli_opts.opt_removed_from_remote:
                if branches_to_slide_out or cli_opts.opt_down_fork_point or cli_opts.opt_merge or cli_opts.opt_no_interactive_rebase:
                    raise MacheteException("Only `--delete` can be passed with `--removed-from-remote`")
                slide_out_client.slide_out_removed_from_remote(opt_delete=cli_opts.opt_delete)
            else:
                slide_out_client.slide_out(
                    branches_to_slide_out=[LocalBranchShortName.of(branch)
                                           for branch in (branches_to_slide_out or [git.get_current_branch()])],
                    opt_delete=cli_opts.opt_delete,
                    opt_down_fork_point=cli_opts.opt_down_fork_point,
                    opt_merge=cli_opts.opt_merge,
                    opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                    opt_no_edit_merge=cli_opts.opt_no_edit_merge)
        elif cmd == "squash":
            squash_client = SquashMacheteClient(git)
            squash_client.read_branch_layout_file()
            current_branch = git.get_current_branch()
            if cli_opts.opt_fork_point is not None:
                squash_client.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                    fork_point=cli_opts.opt_fork_point, branch=current_branch)

            squash_fork_point = cli_opts.opt_fork_point or squash_client.fork_point_or_none(branch=current_branch, use_overrides=True)
            if squash_fork_point is None:
                raise MacheteException(
                    f"git-machete cannot determine the range of commits unique to branch <b>{current_branch}</b>.\n"
                    f"Use `git machete squash --fork-point=...` to select the commit "
                    f"after which the commits of <b>{current_branch}</b> start.\n"
                    "For example, if you want to squash 3 latest commits, use `git machete squash --fork-point=HEAD~3`."
                )
            squash_client.squash(current_branch=current_branch, opt_fork_point=squash_fork_point)
        elif cmd in {"status", alias_by_command["status"]}:
            status_client = MacheteClient(git)
            opt_squash_merge_detection = SquashMergeDetection.from_string(
                cli_opts.opt_squash_merge_detection_string, cli_opts.opt_squash_merge_detection_origin)

            status_client.read_branch_layout_file(interactively_slide_out_invalid_branches=utils.is_stdout_a_tty())
            status_client.expect_at_least_one_managed_branch()
            status_client.status(
                warn_when_branch_in_sync_but_fork_point_off=True,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_list_commits_with_hashes=cli_opts.opt_list_commits_with_hashes,
                opt_squash_merge_detection=opt_squash_merge_detection)
        elif cmd in {"traverse", alias_by_command["traverse"]}:
            if cli_opts.opt_return_to not in {"here", "nearest-remaining", "stay"}:
                raise MacheteException(f"Invalid value for `--return-to` flag: `{cli_opts.opt_return_to}`. "
                                       "Valid values are here, nearest-remaining, stay")
            if cli_opts.opt_start_from not in {"here", "root", "first-root"}:
                raise MacheteException(f"Invalid value for `--start-from` flag: `{cli_opts.opt_start_from}`. "
                                       "Valid values are here, root, first-root")
            opt_return_to = TraverseReturnTo.from_string(cli_opts.opt_return_to, "`--return-to` flag")
            opt_squash_merge_detection = SquashMergeDetection.from_string(
                cli_opts.opt_squash_merge_detection_string, cli_opts.opt_squash_merge_detection_origin)
            opt_start_from = TraverseStartFrom.from_string(cli_opts.opt_start_from, "`--start-from` flag")

            spec = GITHUB_CLIENT_SPEC if cli_opts.opt_sync_github_prs else GITLAB_CLIENT_SPEC
            traverse_client = TraverseMacheteClient(git, spec)
            traverse_client.read_branch_layout_file(interactively_slide_out_invalid_branches=utils.is_stdout_a_tty())
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
                opt_sync_github_prs=cli_opts.opt_sync_github_prs,
                opt_sync_gitlab_mrs=cli_opts.opt_sync_gitlab_mrs,
                opt_yes=cli_opts.opt_yes)
        elif cmd == "update":
            update_client = UpdateMacheteClient(git)
            update_client.read_branch_layout_file()
            if cli_opts.opt_fork_point is not None:
                update_client.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                    fork_point=cli_opts.opt_fork_point, branch=git.get_current_branch())
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
        if initial_current_directory and not utils.does_directory_exist(initial_current_directory):
            nearest_existing_parent_directory = initial_current_directory
            while not utils.does_directory_exist(nearest_existing_parent_directory):
                nearest_existing_parent_directory = os.path.join(
                    nearest_existing_parent_directory, os.path.pardir)
            warn(f"current directory {initial_current_directory} no longer exists, "
                 f"the nearest existing parent directory is {os.path.abspath(nearest_existing_parent_directory)}")


def main() -> None:
    try:
        launch(sys.argv[1:])
    except EOFError:  # pragma: no cover
        sys.exit(ExitCode.END_OF_FILE_SIGNAL)
    except KeyboardInterrupt:  # pragma: no cover
        sys.exit(ExitCode.KEYBOARD_INTERRUPT)
    except (MacheteException, UnderlyingGitException) as e:
        print(e, file=sys.stderr)
        sys.exit(ExitCode.MACHETE_EXCEPTION)
    except InteractionStopped:  # pragma: no cover
        pass


if __name__ == "__main__":
    main()
