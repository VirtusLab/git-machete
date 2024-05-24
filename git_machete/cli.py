#!/usr/bin/env python3

import argparse
import os
import pkgutil
import re
import sys
import textwrap
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypeVar, Union

import git_machete.options
from git_machete import __version__, git_config_keys, utils
from git_machete.constants import SquashMergeDetection
from git_machete.github import GitHubClient
from git_machete.gitlab import GitLabClient

from .client import MacheteClient
from .exceptions import (ExitCode, InteractionStopped, MacheteException,
                         UnderlyingGitException, UnexpectedMacheteException)
from .generated_docs import long_docs, short_docs
from .git_operations import (AnyBranchName, AnyRevision, GitContext,
                             LocalBranchShortName, RemoteBranchShortName)
from .utils import bold, excluding, fmt, underline, warn

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


def get_help_description(display_help_topics: bool, command: Optional[str] = None) -> str:
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
    def __init__(
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

    def __call__(
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

    cli_parser = argparse.ArgumentParser(
        prog='git machete',
        argument_default=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])

    subparsers = cli_parser.add_subparsers(dest='command')

    add_parser = subparsers.add_parser(
        'add',
        argument_default=argparse.SUPPRESS,
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    add_parser.add_argument('branch', nargs='?')
    add_parser.add_argument('-f', '--as-first-child', action='store_true')
    add_parser.add_argument('-o', '--onto')
    add_parser.add_argument('-R', '--as-root', action='store_true')
    add_parser.add_argument('-y', '--yes', action='store_true')

    advance_parser = subparsers.add_parser(
        'advance',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    advance_parser.add_argument('-y', '--yes', action='store_true', default=argparse.SUPPRESS)

    anno_parser = subparsers.add_parser(
        'anno',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    # possible values of 'annotation_text' include: [], [''], ['some_val'], ['text_1', 'text_2']
    anno_parser.add_argument('annotation_text', nargs='*')
    anno_parser.add_argument('-b', '--branch', default=argparse.SUPPRESS)
    anno_parser.add_argument('-H', '--sync-github-prs', action='store_true', default=argparse.SUPPRESS)
    anno_parser.add_argument('-L', '--sync-gitlab-mrs', action='store_true', default=argparse.SUPPRESS)

    clean_parser = subparsers.add_parser(
        'clean',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    clean_parser.add_argument('-H', '--checkout-my-github-prs', action='store_true', default=argparse.SUPPRESS)
    clean_parser.add_argument('-y', '--yes', action='store_true', default=argparse.SUPPRESS)

    completion_parser = subparsers.add_parser(
        'completion',
        argument_default=argparse.SUPPRESS,
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    completion_parser.add_argument('shell', choices=['bash', 'fish', 'zsh'])

    delete_unmanaged_parser = subparsers.add_parser(
        'delete-unmanaged',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    delete_unmanaged_parser.add_argument('-y', '--yes', action='store_true', default=argparse.SUPPRESS)

    diff_full_parser = subparsers.add_parser(
        'diff',
        aliases=['d'],
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    diff_full_parser.add_argument('branch', nargs='?')
    diff_full_parser.add_argument('-s', '--stat', action='store_true', default=argparse.SUPPRESS)

    discover_parser = subparsers.add_parser(
        'discover',
        argument_default=argparse.SUPPRESS,
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    discover_parser.add_argument('-C', '--checked-out-since')
    discover_parser.add_argument('-l', '--list-commits', action='store_true')
    discover_parser.add_argument('-r', '--roots')
    discover_parser.add_argument('-y', '--yes', action='store_true')

    subparsers.add_parser(
        'edit',
        aliases=['e'],
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])

    subparsers.add_parser(
        'file',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])

    fork_point_parser = subparsers.add_parser(
        'fork-point',
        argument_default=argparse.SUPPRESS,
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    fork_point_parser.add_argument('branch', nargs='?')
    fork_point_exclusive_optional_args = fork_point_parser.add_mutually_exclusive_group()
    fork_point_exclusive_optional_args.add_argument('--inferred', action='store_true')
    fork_point_exclusive_optional_args.add_argument('--override-to')
    fork_point_exclusive_optional_args.add_argument('--override-to-inferred', action='store_true')
    fork_point_exclusive_optional_args.add_argument('--override-to-parent', action='store_true')
    fork_point_exclusive_optional_args.add_argument('--unset-override', action='store_true')

    def add_code_hosting_parser(command: str, subcommand_suffix: str, include_sync: bool) -> Any:
        parser = subparsers.add_parser(
            command,
            argument_default=argparse.SUPPRESS,
            usage=argparse.SUPPRESS,
            add_help=False,
            parents=[common_args_parser])
        parser.add_argument('subcommand', choices=[
            f'anno-{subcommand_suffix}s',
            f'checkout-{subcommand_suffix}s',
            f'create-{subcommand_suffix}',
            f'restack-{subcommand_suffix}',
            f'retarget-{subcommand_suffix}'
        ] + (['sync'] if include_sync else []))
        parser.add_argument('request_id', nargs='*', type=int)
        parser.add_argument('-b', '--branch')
        parser.add_argument('--all', action='store_true')
        parser.add_argument('--by')
        parser.add_argument('--draft', action='store_true')
        parser.add_argument('--ignore-if-missing', action='store_true')
        parser.add_argument('--mine', action='store_true')
        parser.add_argument('--title')
        parser.add_argument('--with-urls', action='store_true')
        parser.add_argument('--yes', action='store_true')
    add_code_hosting_parser('github', 'pr', include_sync=True)
    add_code_hosting_parser('gitlab', 'mr', include_sync=False)

    go_parser = subparsers.add_parser(
        'go',
        aliases=['g'],
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    go_parser.add_argument(
        'direction',
        choices=['d', 'down', 'f', 'first', 'l', 'last', 'n', 'next',
                 'p', 'prev', 'r', 'root', 'u', 'up']
    )

    help_parser = subparsers.add_parser(
        'help',
        add_help=False,
        usage=argparse.SUPPRESS,
        parents=[common_args_parser])
    help_parser.add_argument('topic_or_cmd', nargs='?', choices=commands_and_aliases)

    is_managed_parser = subparsers.add_parser(
        'is-managed',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    is_managed_parser.add_argument('branch', nargs='?')

    list_parser = subparsers.add_parser(
        'list',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    list_parser.add_argument(
        'category',
        choices=[
            'addable', 'childless', 'managed', 'slidable', 'slidable-after', 'unmanaged',
            'with-overridden-fork-point']
    )
    list_parser.add_argument('branch', nargs='?', default=argparse.SUPPRESS)

    log_parser = subparsers.add_parser(
        'log',
        aliases=['l'],
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    log_parser.add_argument('branch', nargs='?', default=argparse.SUPPRESS)

    reapply_parser = subparsers.add_parser(
        'reapply',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    reapply_parser.add_argument('-f', '--fork-point', default=argparse.SUPPRESS)

    show_parser = subparsers.add_parser(
        'show',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    show_parser.add_argument(
        'direction',
        choices=['c', 'current', 'd', 'down', 'f', 'first', 'l', 'last',
                 'n', 'next', 'p', 'prev', 'r', 'root', 'u', 'up']
    )
    show_parser.add_argument('branch', nargs='?', default=argparse.SUPPRESS)

    slide_out_parser = subparsers.add_parser(
        'slide-out',
        argument_default=argparse.SUPPRESS,
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    slide_out_parser.add_argument('branches', nargs='*')
    slide_out_parser.add_argument('-d', '--down-fork-point')
    slide_out_parser.add_argument('--delete', action='store_true')
    slide_out_parser.add_argument('-M', '--merge', action='store_true')
    slide_out_parser.add_argument('-n', action='store_true')
    slide_out_parser.add_argument('--no-edit-merge', action='store_true')
    slide_out_parser.add_argument('--no-interactive-rebase', action='store_true')
    slide_out_parser.add_argument('--removed-from-remote', action='store_true')

    squash_parser = subparsers.add_parser(
        'squash',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    squash_parser.add_argument('-f', '--fork-point', default=argparse.SUPPRESS)

    status_parser = subparsers.add_parser(
        'status',
        aliases=['s'],
        argument_default=argparse.SUPPRESS,
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    status_parser.add_argument('--color', choices=['always', 'auto', 'never'], default='auto')
    status_parser.add_argument('-l', '--list-commits', action='store_true')
    status_parser.add_argument('-L', '--list-commits-with-hashes', action='store_true')
    status_parser.add_argument('--no-detect-squash-merges', action='store_true')
    status_parser.add_argument('--squash-merge-detection')

    traverse_parser = subparsers.add_parser(
        'traverse',
        aliases=['t'],
        argument_default=argparse.SUPPRESS,
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    traverse_parser.add_argument('-F', '--fetch', action='store_true')
    traverse_parser.add_argument('-l', '--list-commits', action='store_true')
    traverse_parser.add_argument('-M', '--merge', action='store_true')
    traverse_parser.add_argument('-n', action='store_true')
    traverse_parser.add_argument('--no-edit-merge', action='store_true')
    traverse_parser.add_argument('--no-interactive-rebase', action='store_true')
    traverse_parser.add_argument('--no-detect-squash-merges', action='store_true')
    traverse_parser.add_argument('--squash-merge-detection')
    traverse_parser.add_argument('--push', action='store_true')
    traverse_parser.add_argument('--no-push', action='store_true')
    traverse_parser.add_argument('--push-untracked', action='store_true')
    traverse_parser.add_argument('--no-push-untracked', action='store_true')
    traverse_parser.add_argument('--return-to')
    traverse_parser.add_argument('--start-from')
    traverse_parser.add_argument('-w', '--whole', action='store_true')
    traverse_parser.add_argument('-W', action='store_true')
    traverse_parser.add_argument('-y', '--yes', action='store_true')

    update_parser = subparsers.add_parser(
        'update',
        argument_default=argparse.SUPPRESS,
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])
    update_parser.add_argument('-f', '--fork-point')
    update_parser.add_argument('-M', '--merge', action='store_true')
    update_parser.add_argument('-n', action='store_true')
    update_parser.add_argument('--no-edit-merge', action='store_true')
    update_parser.add_argument('--no-interactive-rebase', action='store_true')

    subparsers.add_parser(
        'version',
        usage=argparse.SUPPRESS,
        add_help=False,
        parents=[common_args_parser])

    return cli_parser


def update_cli_options_using_parsed_args(
        cli_opts: git_machete.options.CommandLineOptions,
        parsed_args: argparse.Namespace) -> None:
    # Warning: In mypy, Arguments that come from untyped functions/variables are silently treated by mypy as Any.
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
        if opt == "as_first_child":
            cli_opts.opt_as_first_child = True
        elif opt == "as_root":
            cli_opts.opt_as_root = True
        elif opt == "branch":
            cli_opts.opt_branch = AnyBranchName.of(arg) if arg else None
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
        elif opt == "inferred":
            cli_opts.opt_inferred = True
        elif opt == "list_commits":
            cli_opts.opt_list_commits = True
        elif opt == "list_commits_with_hashes":
            cli_opts.opt_list_commits = cli_opts.opt_list_commits_with_hashes = True
        elif opt == "merge":
            cli_opts.opt_merge = True
        elif opt == "n":
            cli_opts.opt_n = True
        elif opt == "no_detect_squash_merges":
            warn("`--no-detect-squash-merges` is deprecated, use `--squash-merge-detection=none` instead", end="\n\n")
            cli_opts.opt_squash_merge_detection_string = "none"
        elif opt == "squash_merge_detection" and arg is not None:  # if no arg is passed, argparse will fail anyway
            cli_opts.opt_squash_merge_detection_string = arg
            cli_opts.opt_squash_merge_detection_origin = "`--squash-merge-detection` flag"
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
        elif opt == "removed_from_remote":
            cli_opts.opt_removed_from_remote = True
        elif opt == "return_to":
            cli_opts.opt_return_to = arg
        elif opt == "roots":
            cli_opts.opt_roots = list(map(LocalBranchShortName.of, filter(None, arg.split(","))))
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


def get_local_branch_short_name_from_arg_or_current_branch(
        branch_from_arg: Optional[AnyBranchName], git_context: GitContext) -> LocalBranchShortName:
    return get_local_branch_short_name_from_arg(branch_from_arg) if branch_from_arg else git_context.get_current_branch()


def get_local_branch_short_name_from_arg(branch_from_arg: AnyBranchName) -> LocalBranchShortName:
    return LocalBranchShortName.of(branch_from_arg.replace('refs/heads/', ''))


def launch(orig_args: List[str]) -> None:
    initial_current_directory: Optional[str] = utils.get_current_directory_or_none()

    try:
        cli_opts = git_machete.options.CommandLineOptions()
        git = GitContext()

        cli_parser: argparse.ArgumentParser = create_cli_parser()
        parsed_cli: argparse.Namespace = cli_parser.parse_args(orig_args)
        parsed_cli_as_dict: Dict[str, Any] = vars(parsed_cli)

        # Let's set up options like debug/verbose before we first start reading `git config`.
        set_utils_global_variables(parsed_cli)
        update_cli_options_using_config_keys(cli_opts, git)
        update_cli_options_using_parsed_args(cli_opts, parsed_cli)
        cli_opts.validate()

        if not orig_args:
            print(get_help_description(display_help_topics=False))
            sys.exit(ExitCode.ARGUMENT_ERROR)

        cmd = parsed_cli.command

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

        machete_client = MacheteClient(git)

        if not os.path.exists(machete_client.branch_layout_file_path):
            # We're opening in "append" and not "write" mode to avoid a race condition:
            # if other process writes to the file between we check the
            # result of `os.path.exists` and call `open`,
            # then open(..., "w") would result in us clearing up the file
            # contents, while open(..., "a") has no effect.
            with open(machete_client.branch_layout_file_path, "a"):
                pass
        elif os.path.isdir(machete_client.branch_layout_file_path):
            # Extremely unlikely case, basically checking if anybody
            # tampered with the repository.
            raise MacheteException(
                f"{machete_client.branch_layout_file_path} is a directory "
                "rather than a regular file, aborting")

        should_perform_interactive_slide_out = MacheteClient.should_perform_interactive_slide_out(cmd)
        if cmd == "add":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            branch = get_local_branch_short_name_from_arg_or_current_branch(cli_opts.opt_branch, git)
            machete_client.add(
                branch=branch,
                opt_onto=cli_opts.opt_onto,
                opt_as_first_child=cli_opts.opt_as_first_child,
                opt_as_root=cli_opts.opt_as_root,
                opt_yes=cli_opts.opt_yes,
                verbose=True,
                switch_head_if_new_branch=True)
        elif cmd == "advance":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            git.expect_no_operation_in_progress()
            current_branch = git.get_current_branch()
            machete_client.expect_in_managed_branches(current_branch)
            machete_client.advance(branch=current_branch, opt_yes=cli_opts.opt_yes)
        elif cmd == "anno":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out,
                                                   verify_branches=False)
            if cli_opts.opt_sync_github_prs:
                machete_client.sync_annotations_to_prs(GitHubClient.spec(), include_urls=False)
            elif cli_opts.opt_sync_gitlab_mrs:
                machete_client.sync_annotations_to_prs(GitLabClient.spec(), include_urls=False)
            else:
                branch = get_local_branch_short_name_from_arg_or_current_branch(cli_opts.opt_branch, git)
                machete_client.expect_in_managed_branches(branch)
                if parsed_cli.annotation_text:
                    machete_client.annotate(branch, parsed_cli.annotation_text)
                else:
                    machete_client.print_annotation(branch)
        elif cmd == "clean":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            if 'checkout_my_github_prs' in parsed_cli:
                machete_client.checkout_pull_requests(GitHubClient.spec(), pr_numbers=[], mine=True)
            machete_client.delete_unmanaged(opt_yes=cli_opts.opt_yes)
            machete_client.delete_untracked(opt_yes=cli_opts.opt_yes)
        elif cmd == "delete-unmanaged":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            machete_client.delete_unmanaged(opt_yes=cli_opts.opt_yes)
        elif cmd in {"diff", alias_by_command["diff"]}:
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            diff_branch = get_local_branch_short_name_from_arg(cli_opts.opt_branch) if (cli_opts.opt_branch is not None) else None
            machete_client.diff(branch=diff_branch, opt_stat=cli_opts.opt_stat)
        elif cmd == "discover":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            machete_client.discover_tree(
                opt_checked_out_since=cli_opts.opt_checked_out_since,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_roots=cli_opts.opt_roots,
                opt_yes=cli_opts.opt_yes)
        elif cmd in {"edit", alias_by_command["edit"]}:
            # No need to read branch layout file.
            machete_client.edit()
        elif cmd == "file":
            # No need to read branch layout file.
            print(os.path.abspath(machete_client.branch_layout_file_path))
        elif cmd == "fork-point":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            branch = get_local_branch_short_name_from_arg_or_current_branch(cli_opts.opt_branch, git)
            machete_client.expect_in_local_branches(branch)
            if cli_opts.opt_inferred:
                print(machete_client.fork_point(branch=branch, use_overrides=False))
            elif cli_opts.opt_override_to:
                machete_client.set_fork_point_override(branch, AnyRevision.of(cli_opts.opt_override_to))
            elif cli_opts.opt_override_to_inferred:
                fork_point = machete_client.fork_point(branch=branch, use_overrides=False)
                machete_client.set_fork_point_override(branch, fork_point)
            elif cli_opts.opt_override_to_parent:
                upstream = machete_client.up_branch_for(branch)
                if upstream:
                    machete_client.set_fork_point_override(branch, upstream)
                else:
                    raise MacheteException(
                        f"Branch {bold(branch)} does not have upstream (parent) branch")
            elif cli_opts.opt_unset_override:
                machete_client.unset_fork_point_override(branch)
            else:
                print(machete_client.fork_point(branch=branch, use_overrides=True))
        elif cmd in {"go", alias_by_command["go"]}:
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            git.expect_no_operation_in_progress()
            current_branch = git.get_current_branch()
            dest = machete_client.parse_direction(parsed_cli.direction, current_branch, allow_current=False, down_pick_mode=True)[0]
            # with down_pick_mode=True there is only one element in list allowed
            if dest != current_branch:
                git.checkout(dest)
        elif cmd in ("github", "gitlab"):
            subcommand = parsed_cli.subcommand
            config = GitHubClient.spec() if cmd == "github" else GitLabClient.spec()
            subcommand_suffix = "pr" if cmd == "github" else "mr"

            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)

            if 'request_id' in parsed_cli and subcommand != f'checkout-{subcommand_suffix}s':
                raise MacheteException(f"`request_id` option is only valid with `checkout-{subcommand_suffix}s` subcommand.")
            for command in ('all', 'by', 'mine'):
                if command in parsed_cli and subcommand != f"checkout-{subcommand_suffix}s":
                    raise MacheteException(f"`--{command}` option is only valid with `checkout-{subcommand_suffix}s` subcommand.")
            if "branch" in parsed_cli and subcommand != f"retarget-{subcommand_suffix}":
                raise MacheteException(f"`--branch` option is only valid with `retarget-{subcommand_suffix}` subcommand.")
            if "draft" in parsed_cli and subcommand != f"create-{subcommand_suffix}":
                raise MacheteException(f"`--draft` option is only valid with `create-{subcommand_suffix}` subcommand.")
            if "ignore_if_missing" in parsed_cli and subcommand != f"retarget-{subcommand_suffix}":
                raise MacheteException(f"`--ignore-if-missing` option is only valid with `retarget-{subcommand_suffix}` subcommand.")
            if "title" in parsed_cli and subcommand != f"create-{subcommand_suffix}":
                raise MacheteException(f"`--title` option is only valid with `create-{subcommand_suffix}` subcommand.")
            if "with_urls" in parsed_cli and subcommand != f"anno-{subcommand_suffix}s":
                raise MacheteException(f"`--with-urls` option is only valid with `anno-{subcommand_suffix}s` subcommand.")
            if "yes" in parsed_cli and subcommand != f"create-{subcommand_suffix}":
                raise MacheteException(f"`--yes` option is only valid with `create-{subcommand_suffix}` subcommand.")

            if subcommand == f"anno-{subcommand_suffix}s":
                machete_client.sync_annotations_to_prs(config, include_urls=cli_opts.opt_with_urls)
            elif subcommand == f"checkout-{subcommand_suffix}s":
                if len(set(parsed_cli_as_dict.keys()).intersection({'all', 'by', 'mine', 'request_id'})) != 1:
                    raise MacheteException(f"`checkout-{subcommand_suffix}s` subcommand must take exactly one of the following options: " +
                                           ', '.join(['--all', '--by=...', '--mine', f'{subcommand_suffix}-number(s)']))
                machete_client.checkout_pull_requests(config,
                                                      pr_numbers=parsed_cli.request_id if 'request_id' in parsed_cli else [],
                                                      all=parsed_cli.all if 'all' in parsed_cli else False,
                                                      mine=parsed_cli.mine if 'mine' in parsed_cli else False,
                                                      by=parsed_cli.by if 'by' in parsed_cli else None,
                                                      fail_on_missing_current_user_for_my_opened_prs=True)
            elif subcommand == f"create-{subcommand_suffix}":
                current_branch = git.get_current_branch()
                machete_client.create_pull_request(
                    config,
                    head=current_branch,
                    opt_draft=cli_opts.opt_draft,
                    opt_onto=cli_opts.opt_onto,
                    opt_title=cli_opts.opt_title,
                    opt_yes=cli_opts.opt_yes)
            elif subcommand == f"restack-{subcommand_suffix}":
                machete_client.restack_pull_request(config)
            elif subcommand == f"retarget-{subcommand_suffix}":
                branch = parsed_cli.branch if 'branch' in parsed_cli else git.get_current_branch()
                machete_client.expect_in_managed_branches(branch)
                ignore_if_missing = parsed_cli.ignore_if_missing if 'ignore_if_missing' in parsed_cli else False
                machete_client.retarget_pr(config, head=branch, ignore_if_missing=ignore_if_missing)
            elif subcommand == "sync":  # GitHub only
                machete_client.checkout_pull_requests(config, pr_numbers=[], mine=True)
                machete_client.delete_unmanaged(opt_yes=False)
                machete_client.delete_untracked(opt_yes=cli_opts.opt_yes)
            else:  # an unknown subcommand is handled by argparse
                raise UnexpectedMacheteException(f"Unknown subcommand: `{subcommand}`")
        elif cmd == "is-managed":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            branch = get_local_branch_short_name_from_arg_or_current_branch(cli_opts.opt_branch, git)
            if branch is None or branch not in machete_client.managed_branches:
                sys.exit(ExitCode.MACHETE_EXCEPTION)
        elif cmd == "list":
            category = parsed_cli.category
            if category == 'slidable-after' and 'branch' not in parsed_cli_as_dict:
                raise MacheteException(f"`git machete list {category}` requires an extra <branch> argument")
            elif category != 'slidable-after' and 'branch' in parsed_cli_as_dict:
                raise MacheteException(f"`git machete list {category}` does not expect extra arguments")

            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            res = []
            if category == "addable":
                def strip_remote_name(remote_branch: RemoteBranchShortName) -> LocalBranchShortName:
                    return LocalBranchShortName.of(re.sub("^[^/]+/", "", remote_branch))

                remote_counterparts_of_local_branches = utils.map_truthy_only(
                    git.get_combined_counterpart_for_fetching_of_branch,
                    git.get_local_branches())
                qualifying_remote_branches: List[RemoteBranchShortName] = \
                    excluding(git.get_remote_branches(), remote_counterparts_of_local_branches)
                res = excluding(git.get_local_branches(), machete_client.managed_branches) + list(
                    map(strip_remote_name, qualifying_remote_branches))
            elif category == "childless":
                res = machete_client.get_childless_managed_branches()
            elif category == "managed":
                res = machete_client.managed_branches
            elif category == "slidable":
                res = machete_client.get_slidable_branches()
            elif category == "slidable-after":
                machete_client.expect_in_managed_branches(parsed_cli.branch)
                res = machete_client.get_slidable_after(parsed_cli.branch)
            elif category == "unmanaged":
                res = excluding(git.get_local_branches(), machete_client.managed_branches)
            elif category == "with-overridden-fork-point":
                res = list(
                    filter(
                        lambda _branch: machete_client.has_any_fork_point_override_config(_branch),
                        git.get_local_branches()))
            else:  # an unknown category is handled by argparse
                raise UnexpectedMacheteException(f"Invalid category: `{category}`")

            if res:
                print("\n".join(res))
        elif cmd in {"log", alias_by_command["log"]}:
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            branch = get_local_branch_short_name_from_arg_or_current_branch(cli_opts.opt_branch, git)
            machete_client.log(branch)
        elif cmd == "reapply":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            git.expect_no_operation_in_progress()
            current_branch = git.get_current_branch()
            if "fork_point" in parsed_cli and cli_opts.opt_fork_point:
                machete_client.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                    fork_point_hash=cli_opts.opt_fork_point, branch=current_branch)

            reapply_fork_point = cli_opts.opt_fork_point or machete_client.fork_point(branch=current_branch, use_overrides=True)
            machete_client.rebase(reapply_fork_point, reapply_fork_point, current_branch, cli_opts.opt_no_interactive_rebase)
        elif cmd == "show":
            direction = parsed_cli.direction
            if direction == "current" and "branch" in parsed_cli:
                raise MacheteException('`show current` with a `<branch>` argument does not make sense')
            branch = get_local_branch_short_name_from_arg_or_current_branch(cli_opts.opt_branch, git)
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out,
                                                   verify_branches=False)
            print('\n'.join(machete_client.parse_direction(direction, branch, allow_current=True, down_pick_mode=False)))
        elif cmd == "slide-out":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            git.expect_no_operation_in_progress()
            branches_to_slide_out: Optional[List[str]] = parsed_cli_as_dict.get('branches')
            if cli_opts.opt_removed_from_remote:
                if branches_to_slide_out or cli_opts.opt_down_fork_point or cli_opts.opt_merge or cli_opts.opt_no_interactive_rebase:
                    raise MacheteException("Only `--delete` can be passed with `--removed-from-remote`")
                machete_client.slide_out_removed_from_remote(opt_delete=cli_opts.opt_delete)
            else:
                machete_client.slide_out(
                    branches_to_slide_out=list(map(LocalBranchShortName.of, branches_to_slide_out or [git.get_current_branch()])),
                    opt_delete=cli_opts.opt_delete,
                    opt_down_fork_point=cli_opts.opt_down_fork_point,
                    opt_merge=cli_opts.opt_merge,
                    opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                    opt_no_edit_merge=cli_opts.opt_no_edit_merge)
        elif cmd == "squash":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            git.expect_no_operation_in_progress()
            current_branch = git.get_current_branch()
            if "fork_point" in parsed_cli and cli_opts.opt_fork_point:
                machete_client.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                    fork_point_hash=cli_opts.opt_fork_point, branch=current_branch)

            squash_fork_point = cli_opts.opt_fork_point or machete_client.fork_point_or_none(branch=current_branch, use_overrides=True)
            if squash_fork_point is None:
                raise MacheteException(
                    f"git-machete cannot determine the range of commits unique to branch <b>{current_branch}</b>.\n"
                    f"Use `git machete squash --fork-point=...` to select the commit "
                    f"after which the commits of <b>{current_branch}</b> start.\n"
                    "For example, if you want to squash 3 latest commits, use `git machete squash --fork-point=HEAD~3`."
                )
            machete_client.squash(current_branch=current_branch, opt_fork_point=squash_fork_point)
        elif cmd in {"status", alias_by_command["status"]}:
            opt_squash_merge_detection = SquashMergeDetection.from_string(
                cli_opts.opt_squash_merge_detection_string, cli_opts.opt_squash_merge_detection_origin)

            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            machete_client.expect_at_least_one_managed_branch()
            machete_client.status(
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
            opt_squash_merge_detection = SquashMergeDetection.from_string(
                cli_opts.opt_squash_merge_detection_string, cli_opts.opt_squash_merge_detection_origin)

            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            git.expect_no_operation_in_progress()
            machete_client.traverse(
                opt_fetch=cli_opts.opt_fetch,
                opt_list_commits=cli_opts.opt_list_commits,
                opt_merge=cli_opts.opt_merge,
                opt_no_edit_merge=cli_opts.opt_no_edit_merge,
                opt_no_interactive_rebase=cli_opts.opt_no_interactive_rebase,
                opt_push_tracked=cli_opts.opt_push_tracked,
                opt_push_untracked=cli_opts.opt_push_untracked,
                opt_return_to=cli_opts.opt_return_to,
                opt_squash_merge_detection=opt_squash_merge_detection,
                opt_start_from=cli_opts.opt_start_from,
                opt_yes=cli_opts.opt_yes)
        elif cmd == "update":
            machete_client.read_branch_layout_file(perform_interactive_slide_out=should_perform_interactive_slide_out)
            git.expect_no_operation_in_progress()
            if "fork_point" in parsed_cli and cli_opts.opt_fork_point:
                machete_client.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                    fork_point_hash=cli_opts.opt_fork_point, branch=git.get_current_branch())
            machete_client.update(
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
    except EOFError:
        sys.exit(ExitCode.END_OF_FILE_SIGNAL)
    except KeyboardInterrupt:
        sys.exit(ExitCode.KEYBOARD_INTERRUPT)
    except (MacheteException, UnderlyingGitException) as e:
        print(e, file=sys.stderr)
        sys.exit(ExitCode.MACHETE_EXCEPTION)
    except InteractionStopped:  # pragma: no cover
        pass


if __name__ == "__main__":
    main()
