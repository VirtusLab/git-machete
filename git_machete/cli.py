#!/usr/bin/env python

import getopt
import os
import re
import sys
import textwrap
from typing import Dict, List, Optional, Tuple, TypeVar

import git_machete.options
from git_machete import __version__
from git_machete import utils
from git_machete.client import MacheteClient, allowed_directions
from git_machete.constants import EscapeCodes
from git_machete.docs import short_docs, long_docs
from git_machete.exceptions import MacheteException, StopTraversal
from git_machete.git_operations import GitContext
from git_machete.utils import fmt, underline, excluding, warn

T = TypeVar('T')

initial_current_directory: Optional[str] = utils.get_current_directory_or_none() or os.getenv('PWD')

alias_by_command: Dict[str, str] = {
    "diff": "d",
    "edit": "e",
    "go": "g",
    "log": "l",
    "status": "s"
}
command_by_alias: Dict[str, str] = {v: k for k, v in alias_by_command.items()}

command_groups: List[Tuple[str, List[str]]] = [
    # 'is-managed' is mostly for scripting use and therefore skipped
    ("General topics",
     ["file", "help", "hooks", "version"]),
    ("Build, display and modify the tree of branch dependencies",
     ["add", "anno", "discover", "edit", "status"]),
    ("List, check out and delete branches",
     ["delete-unmanaged", "go", "list", "show"]),
    ("Determine changes specific to the given branch",
     ["diff", "fork-point", "log"]),
    ("Update git history in accordance with the tree of branch dependencies",
     ["advance", "reapply", "slide-out", "squash", "traverse", "update"])
]


def usage(command: str = None) -> None:
    if command and command in command_by_alias:
        command = command_by_alias[command]
    if command and command in long_docs:
        print(fmt(textwrap.dedent(long_docs[command])))
    else:
        print()
        short_usage()
        if command:
            print(f"\nUnknown command: '{command}'")
        print(fmt("\n<u>TL;DR tip</u>\n\n"
                  "    Get familiar with the help for <b>format</b>, <b>edit</b>,"
                  " <b>status</b> and <b>update</b>, in this order.\n"))
        for hdr, cmds in command_groups:
            print(underline(hdr))
            print()
            for cm in cmds:
                alias = f", {alias_by_command[cm]}" if cm in alias_by_command else ""
                print("    %s%-18s%s%s" % (EscapeCodes.BOLD, cm + alias, EscapeCodes.ENDC, short_docs[
                    cm]))  # bold(...) can't be used here due to the %-18s format specifier
            sys.stdout.write("\n")
        print(fmt(textwrap.dedent("""
            <u>General options</u>\n
                <b>--debug</b>           Log detailed diagnostic info, including outputs of the executed git commands.
                <b>-h, --help</b>        Print help and exit.
                <b>-v, --verbose</b>     Log the executed git commands.
                <b>--version</b>         Print version and exit.
        """[1:])))


def short_usage() -> None:
    print(
        fmt("<b>Usage: git machete [--debug] [-h] [-v|--verbose] [--version] "
            "<command> [command-specific options] [command-specific argument]</b>"))


def version() -> None:
    print(f"git-machete version {__version__}")


def main() -> None:
    launch(sys.argv[1:])


def launch(orig_args: List[str]) -> None:
    cli_opts = git_machete.options.CommandLineOptions()
    git = GitContext(cli_opts)

    if sys.version_info.major == 2 or (sys.version_info.major == 3 and sys.version_info.minor < 6):
        version_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        sys.stderr.write(
            f"Python {version_str} is no longer supported. Please switch to Python 3.6 or higher.\n")
        sys.exit(1)

    def parse_options(in_args: List[str], short_opts: str = "", long_opts: List[str] = [],
                      allow_intermixing_options_and_params: bool = True) -> List[str]:

        fun = getopt.gnu_getopt if allow_intermixing_options_and_params else getopt.getopt
        opts, rest = fun(in_args, short_opts + "hv",
                         long_opts + ['debug', 'help', 'verbose', 'version'])

        for opt, arg in opts:
            if opt in ("-b", "--branch"):
                cli_opts.opt_branch = arg
            elif opt in ("-C", "--checked-out-since"):
                cli_opts.opt_checked_out_since = arg
            elif opt == "--color":
                cli_opts.opt_color = arg
            elif opt in ("-d", "--down-fork-point"):
                cli_opts.opt_down_fork_point = arg
            elif opt == "--debug":
                git_machete.options.CommandLineOptions.opt_debug = True
            elif opt == "--draft":
                cli_opts.opt_draft = True
            elif opt in ("-F", "--fetch"):
                cli_opts.opt_fetch = True
            elif opt in ("-f", "--fork-point"):
                cli_opts.opt_fork_point = arg
            elif opt in ("-H", "--sync-github-prs"):
                cli_opts.opt_sync_github_prs = True
            elif opt in ("-h", "--help"):
                usage(cmd)
                sys.exit()
            elif opt == "--inferred":
                cli_opts.opt_inferred = True
            elif opt in ("-L", "--list-commits-with-hashes"):
                cli_opts.opt_list_commits = cli_opts.opt_list_commits_with_hashes = True
            elif opt in ("-l", "--list-commits"):
                cli_opts.opt_list_commits = True
            elif opt in ("-M", "--merge"):
                cli_opts.opt_merge = True
            elif opt == "-n":
                cli_opts.opt_n = True
            elif opt == "--no-detect-squash-merges":
                cli_opts.opt_no_detect_squash_merges = True
            elif opt == "--no-edit-merge":
                cli_opts.opt_no_edit_merge = True
            elif opt == "--no-interactive-rebase":
                cli_opts.opt_no_interactive_rebase = True
            elif opt == "--no-push":
                cli_opts.opt_push_tracked = False
                cli_opts.opt_push_untracked = False
            elif opt == "--no-push-untracked":
                cli_opts.opt_push_untracked = False
            elif opt in ("-o", "--onto"):
                cli_opts.opt_onto = arg
            elif opt == "--override-to":
                cli_opts.opt_override_to = arg
            elif opt == "--override-to-inferred":
                cli_opts.opt_override_to_inferred = True
            elif opt == "--override-to-parent":
                cli_opts.opt_override_to_parent = True
            elif opt == "--push":
                cli_opts.opt_push_tracked = True
                cli_opts.opt_push_untracked = True
            elif opt == "--push-untracked":
                cli_opts.opt_push_untracked = True
            elif opt in ("-R", "--as-root"):
                cli_opts.opt_as_root = True
            elif opt in ("-r", "--roots"):
                cli_opts.opt_roots = arg.split(",")
            elif opt == "--return-to":
                cli_opts.opt_return_to = arg
            elif opt in ("-s", "--stat"):
                cli_opts.opt_stat = True
            elif opt == "--start-from":
                cli_opts.opt_start_from = arg
            elif opt == "--unset-override":
                cli_opts.opt_unset_override = True
            elif opt in ("-v", "--verbose"):
                git_machete.options.CommandLineOptions.opt_verbose = True
            elif opt == "--version":
                version()
                sys.exit()
            elif opt == "-W":
                cli_opts.opt_fetch = True
                cli_opts.opt_start_from = "first-root"
                cli_opts.opt_n = True
                cli_opts.opt_return_to = "nearest-remaining"
            elif opt in ("-w", "--whole"):
                cli_opts.opt_start_from = "first-root"
                cli_opts.opt_n = True
                cli_opts.opt_return_to = "nearest-remaining"
            elif opt in ("-y", "--yes"):
                cli_opts.opt_yes = cli_opts.opt_no_interactive_rebase = True

        if cli_opts.opt_color not in ("always", "auto", "never"):
            raise MacheteException(
                "Invalid argument for `--color`. Valid arguments: `always|auto|never`.")
        else:
            utils.ascii_only = (
                cli_opts.opt_color == "never" or (
                    cli_opts.opt_color == "auto" and not sys.stdout.isatty())
            )

        if cli_opts.opt_as_root and cli_opts.opt_onto:
            raise MacheteException(
                "Option `-R/--as-root` cannot be specified together with `-o/--onto`.")

        if cli_opts.opt_no_edit_merge and not cli_opts.opt_merge:
            raise MacheteException(
                "Option `--no-edit-merge` only makes sense when using merge and must be specified together with `-M/--merge`.")
        if cli_opts.opt_no_interactive_rebase and cli_opts.opt_merge:
            raise MacheteException(
                "Option `--no-interactive-rebase` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")
        if cli_opts.opt_down_fork_point and cli_opts.opt_merge:
            raise MacheteException(
                "Option `-d/--down-fork-point` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")
        if cli_opts.opt_fork_point and cli_opts.opt_merge:
            raise MacheteException(
                "Option `-f/--fork-point` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")

        if cli_opts.opt_n and cli_opts.opt_merge:
            cli_opts.opt_no_edit_merge = True
        if cli_opts.opt_n and not cli_opts.opt_merge:
            cli_opts.opt_no_interactive_rebase = True

        return rest

    def expect_no_param(in_args: List[str], extra_explanation: str = '') -> None:
        if len(in_args) > 0:
            raise MacheteException(f"No argument expected for `{cmd}`{extra_explanation}")

    def check_optional_param(in_args: List[str]) -> Optional[str]:
        if not in_args:
            return None
        elif len(in_args) > 1:
            raise MacheteException(f"`{cmd}` accepts at most one argument")
        elif not in_args[0]:
            raise MacheteException(f"Argument to `{cmd}` cannot be empty")
        elif in_args[0][0] == "-":
            raise MacheteException(f"Option `{in_args[0]}` not recognized")
        else:
            return in_args[0]

    def check_required_param(in_args: List[str], allowed_values_string: str) -> str:
        if not in_args or len(in_args) > 1:
            raise MacheteException(
                f"`{cmd}` expects exactly one argument: one of {allowed_values_string}")
        elif not in_args[0]:
            raise MacheteException(
                f"Argument to `{cmd}` cannot be empty; expected one of {allowed_values_string}")
        elif in_args[0][0] == "-":
            raise MacheteException(f"Option `{in_args[0]}` not recognized")
        else:
            return in_args[0]

    try:
        machete_client = MacheteClient(cli_opts, git)
        cmd = None
        # Let's first extract the common options like `--help` or `--verbose` that might appear BEFORE the command,
        # as in e.g. `git machete --verbose status`.
        cmd_and_args = parse_options(orig_args, allow_intermixing_options_and_params=False)
        # Subsequent calls to `parse_options` will, in turn, extract the options appearing AFTER the command.
        if not cmd_and_args:
            usage()
            sys.exit(2)
        cmd = cmd_and_args[0]
        args = cmd_and_args[1:]

        if cmd != "help":
            if cmd != "discover":
                if not os.path.exists(machete_client.definition_file_path):
                    # We're opening in "append" and not "write" mode to avoid a race condition:
                    # if other process writes to the file between we check the result of `os.path.exists` and call `open`,
                    # then open(..., "w") would result in us clearing up the file contents, while open(..., "a") has no effect.
                    with open(machete_client.definition_file_path, "a"):
                        pass
                elif os.path.isdir(machete_client.definition_file_path):
                    # Extremely unlikely case, basically checking if anybody tampered with the repository.
                    raise MacheteException(
                        f"{machete_client.definition_file_path} is a directory rather than a regular file, aborting")

        if cmd == "add":
            param = check_optional_param(parse_options(args, "o:Ry", ["onto=", "as-root", "yes"]))
            machete_client.read_definition_file()
            machete_client.add(param or git.get_current_branch())
        elif cmd == "advance":
            args1 = parse_options(args, "y", ["yes"])
            expect_no_param(args1)
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            current_branch = git.get_current_branch()
            machete_client.expect_in_managed_branches(current_branch)
            machete_client.advance(current_branch)
        elif cmd == "anno":
            params = parse_options(args, "b:H", ["branch=", "sync-github-prs"])
            machete_client.read_definition_file(verify_branches=False)
            if cli_opts.opt_sync_github_prs:
                machete_client.sync_annotations_to_github_prs()
            else:
                branch = cli_opts.opt_branch or git.get_current_branch()
                machete_client.expect_in_managed_branches(branch)
                if params:
                    machete_client.annotate(branch, params)
                else:
                    machete_client.print_annotation(branch)
        elif cmd == "delete-unmanaged":
            expect_no_param(parse_options(args, "y", ["yes"]))
            machete_client.read_definition_file()
            machete_client.delete_unmanaged()
        elif cmd in ("d", "diff"):
            param = check_optional_param(parse_options(args, "s", ["stat"]))
            machete_client.read_definition_file()
            machete_client.diff(param)  # passing None if not specified
        elif cmd == "discover":
            expect_no_param(parse_options(args, "C:lr:y",
                                          ["checked-out-since=", "list-commits", "roots=", "yes"]))
            # No need to read definition file.
            machete_client.discover_tree()
        elif cmd in ("e", "edit"):
            expect_no_param(parse_options(args))
            # No need to read definition file.
            machete_client.edit()
        elif cmd == "file":
            expect_no_param(parse_options(args))
            # No need to read definition file.
            print(os.path.abspath(machete_client.definition_file_path))
        elif cmd == "fork-point":
            long_options = ["inferred", "override-to=", "override-to-inferred",
                            "override-to-parent", "unset-override"]
            param = check_optional_param(parse_options(args, "", long_options))
            machete_client.read_definition_file()
            branch = param or git.get_current_branch()
            if len(list(filter(None, [cli_opts.opt_inferred, cli_opts.opt_override_to,
                                      cli_opts.opt_override_to_inferred,
                                      cli_opts.opt_override_to_parent,
                                      cli_opts.opt_unset_override]))) > 1:
                long_options_string = ", ".join(map(lambda x: x.replace("=", ""), long_options))
                raise MacheteException(
                    f"At most one of {long_options_string} options may be present")
            if cli_opts.opt_inferred:
                print(machete_client.fork_point(branch, use_overrides=False))
            elif cli_opts.opt_override_to:
                machete_client.set_fork_point_override(branch, cli_opts.opt_override_to)
            elif cli_opts.opt_override_to_inferred:
                machete_client.set_fork_point_override(branch, machete_client.fork_point(branch,
                                                                                         use_overrides=False))
            elif cli_opts.opt_override_to_parent:
                upstream = machete_client.up_branch.get(branch)
                if upstream:
                    machete_client.set_fork_point_override(branch, upstream)
                else:
                    raise MacheteException(
                        f"Branch {branch} does not have upstream (parent) branch")
            elif cli_opts.opt_unset_override:
                machete_client.unset_fork_point_override(branch)
            else:
                print(machete_client.fork_point(branch, use_overrides=True))
        elif cmd in ("g", "go"):
            param = check_required_param(parse_options(args),
                                         allowed_directions(allow_current=False))
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            current_branch = git.get_current_branch()
            dest = machete_client.parse_direction(param, current_branch, allow_current=False,
                                                  down_pick_mode=True)
            if dest != current_branch:
                git.checkout(dest)
        elif cmd == "github":
            github_allowed_subcommands = "anno-prs|create-pr|retarget-pr"
            param = check_required_param(parse_options(args, "", ["draft"]),
                                         github_allowed_subcommands)
            machete_client.read_definition_file()
            if param == "anno-prs":
                machete_client.sync_annotations_to_github_prs()
            elif param == "create-pr":
                current_branch = git.get_current_branch()
                machete_client.create_github_pr(current_branch, draft=cli_opts.opt_draft)
            elif param == "retarget-pr":
                current_branch = git.get_current_branch()
                machete_client.expect_in_managed_branches(current_branch)
                machete_client.retarget_github_pr(current_branch)
            else:
                raise MacheteException(
                    f"`github` requires a subcommand: one of `{github_allowed_subcommands}`")
        elif cmd == "help":
            param = check_optional_param(parse_options(args))
            # No need to read definition file.
            usage(param)
        elif cmd == "is-managed":
            param = check_optional_param(parse_options(args))
            machete_client.read_definition_file()
            branch = param or git.get_current_branch_or_none()
            if branch is None or branch not in machete_client.managed_branches:
                sys.exit(1)
        elif cmd == "list":
            list_allowed_values = "addable|managed|slidable|slidable-after <branch>|unmanaged|with-overridden-fork-point"
            list_args = parse_options(args)
            if not list_args:
                raise MacheteException(
                    f"`git machete list` expects argument(s): {list_allowed_values}")
            elif not list_args[0]:
                raise MacheteException(
                    f"Argument to `git machete list` cannot be empty; expected {list_allowed_values}")
            elif list_args[0][0] == "-":
                raise MacheteException(f"Option `{list_args[0]}` not recognized")
            elif list_args[0] not in (
                    "addable", "managed", "slidable", "slidable-after", "unmanaged",
                    "with-overridden-fork-point"):
                raise MacheteException(f"Usage: git machete list {list_allowed_values}")
            elif len(list_args) > 2:
                raise MacheteException(f"Too many arguments to `git machete list {list_args[0]}` ")
            elif (list_args[0] in (
                  "addable", "managed", "slidable", "unmanaged", "with-overridden-fork-point") and
                  len(list_args) > 1):
                raise MacheteException(
                    f"`git machete list {list_args[0]}` does not expect extra arguments")
            elif list_args[0] == "slidable-after" and len(list_args) != 2:
                raise MacheteException(
                    f"`git machete list {list_args[0]}` requires an extra <branch> argument")

            param = list_args[0]
            machete_client.read_definition_file()
            res = []
            if param == "addable":
                def strip_first_fragment(remote_branch: str) -> str:
                    return re.sub("^[^/]+/", "", remote_branch)

                remote_counterparts_of_local_branches = utils.map_truthy_only(
                    lambda branch: git.get_combined_counterpart_for_fetching_of_branch(branch),
                    git.get_local_branches())
                qualifying_remote_branches = excluding(git.get_remote_branches(),
                                                       remote_counterparts_of_local_branches)
                res = excluding(git.get_local_branches(), machete_client.managed_branches) + list(
                    map(strip_first_fragment, qualifying_remote_branches))
            elif param == "managed":
                res = machete_client.managed_branches
            elif param == "slidable":
                res = machete_client.slidable()
            elif param == "slidable-after":
                b_arg = list_args[1]
                machete_client.expect_in_managed_branches(b_arg)
                res = machete_client.slidable_after(b_arg)
            elif param == "unmanaged":
                res = excluding(git.get_local_branches(), machete_client.managed_branches)
            elif param == "with-overridden-fork-point":
                res = list(
                    filter(lambda branch: machete_client.has_any_fork_point_override_config(branch),
                           git.get_local_branches()))

            if res:
                print("\n".join(res))
        elif cmd in ("l", "log"):
            param = check_optional_param(parse_options(args))
            machete_client.read_definition_file()
            machete_client.log(param or git.get_current_branch())
        elif cmd == "reapply":
            args1 = parse_options(args, "f:", ["fork-point="])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            current_branch = git.get_current_branch()
            git.rebase_onto_ancestor_commit(current_branch,
                                            cli_opts.opt_fork_point or machete_client.fork_point(
                                                current_branch, use_overrides=True))
        elif cmd == "show":
            args1 = parse_options(args)
            param = check_required_param(args1[:1], allowed_directions(allow_current=True))
            branch = check_optional_param(args1[1:])
            if param == "current" and branch is not None:
                raise MacheteException(
                    f'`show current` with a branch (`{branch}`) does not make sense')
            machete_client.read_definition_file(verify_branches=False)
            print(machete_client.parse_direction(param, branch or git.get_current_branch(),
                                                 allow_current=True, down_pick_mode=False))
        elif cmd == "slide-out":
            params = parse_options(args, "d:Mn", ["down-fork-point=", "merge", "no-edit-merge",
                                                  "no-interactive-rebase"])
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            machete_client.slide_out(params or [git.get_current_branch()])
        elif cmd == "squash":
            args1 = parse_options(args, "f:", ["fork-point="])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            current_branch = git.get_current_branch()
            machete_client.squash(current_branch,
                                  cli_opts.opt_fork_point or machete_client.fork_point(
                                      current_branch, use_overrides=True))
        elif cmd in ("s", "status"):
            expect_no_param(parse_options(args, "Ll",
                                          ["color=", "list-commits-with-hashes", "list-commits",
                                           "no-detect-squash-merges"]))
            machete_client.read_definition_file()
            machete_client.expect_at_least_one_managed_branch()
            machete_client.status(warn_on_yellow_edges=True)
        elif cmd == "traverse":
            traverse_long_opts = ["fetch", "list-commits", "merge",
                                  "no-detect-squash-merges", "no-edit-merge",
                                  "no-interactive-rebase",
                                  "no-push", "no-push-untracked", "push", "push-untracked",
                                  "return-to=", "start-from=", "whole", "yes"]
            expect_no_param(parse_options(args, "FlMnWwy", traverse_long_opts))
            if cli_opts.opt_start_from not in ("here", "root", "first-root"):
                raise MacheteException(
                    "Invalid argument for `--start-from`. Valid arguments: `here|root|first-root`.")
            if cli_opts.opt_return_to not in ("here", "nearest-remaining", "stay"):
                raise MacheteException(
                    "Invalid argument for `--return-to`. Valid arguments: here|nearest-remaining|stay.")
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            machete_client.traverse()
        elif cmd == "update":
            args1 = parse_options(args, "f:Mn", ["fork-point=", "merge", "no-edit-merge",
                                                 "no-interactive-rebase"])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            machete_client.update()
        elif cmd == "version":
            version()
            sys.exit()
        else:
            short_usage()
            raise MacheteException(
                f"\nUnknown command: `{cmd}`. Use `git machete help` to list possible commands")

    except getopt.GetoptError as e:
        short_usage()
        sys.stderr.write(f"\n{e}\n")
        sys.exit(2)
    except MacheteException as e:
        sys.stderr.write(f"\n{e}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted by the user")
        sys.exit(1)
    except StopTraversal:
        pass
    finally:
        if initial_current_directory and not utils.does_directory_exist(initial_current_directory):
            nearest_existing_parent_directory = initial_current_directory
            while not utils.does_directory_exist(nearest_existing_parent_directory):
                nearest_existing_parent_directory = os.path.join(nearest_existing_parent_directory,
                                                                 os.path.pardir)
            warn(f"current directory {initial_current_directory} no longer exists, "
                 f"the nearest existing parent directory is {os.path.abspath(nearest_existing_parent_directory)}")


if __name__ == "__main__":
    main()
