import argparse
import textwrap
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from git_machete import __version__
from git_machete.generated_docs import long_docs, short_docs
from git_machete.utils.exceptions import ExitCode
from git_machete.utils.markup import print_fmt

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
     ["add", "anno", "discover", "edit", "rename", "status"]),
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


def get_short_general_usage() -> str:
    return ("<b>Usage: git machete [--debug] [-h] [-v|--verbose] [--version] "
            "<command> [command-specific options] [command-specific argument]</b>")


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
