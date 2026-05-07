import itertools
from typing import Dict, List, Optional, Tuple

from git_machete.annotation import Annotation
from git_machete.client.state import MacheteState
from git_machete.git_operations import LocalBranchShortName
from git_machete.utils import MacheteException


def parse(path: str) -> Tuple[MacheteState, Optional[str]]:
    """Parse the branch layout file at *path*.

    Returns a new `MacheteState` populated from the file together with
    the indent string detected in the file (`None` when no indented
    line was found, e.g. a single-root flat layout).

    Raises `MacheteException` for structural errors (duplicate branch,
    bad indent, excess depth).
    """
    with open(path) as f:
        lines: List[str] = [line.rstrip() for line in f.readlines()]

    state = MacheteState()
    indent: Optional[str] = None
    at_depth: Dict[int, LocalBranchShortName] = {}
    last_depth = -1
    hint = "Edit the branch layout file manually with `git machete edit`"

    for index, line in enumerate(lines):
        if line == "":
            continue
        # Undocumented: lines whose first non-whitespace character is `#`
        # are ignored as comments.  They are not preserved when
        # git-machete writes the branch layout file.
        if line.lstrip().startswith("#"):
            continue

        prefix = "".join(itertools.takewhile(str.isspace, line))
        if prefix and not indent:
            indent = prefix

        branch_and_maybe_annotation: List[LocalBranchShortName] = [
            LocalBranchShortName.of(entry) for entry in line.strip().split(" ", 1)
        ]
        branch = branch_and_maybe_annotation[0]
        annotation = (
            Annotation.parse(branch_and_maybe_annotation[1])
            if len(branch_and_maybe_annotation) > 1
            else None
        )

        if state.is_managed(branch):
            raise MacheteException(
                f"{path}, line {index + 1}: branch "
                f"<b>{branch}</b> re-appears in the branch layout. {hint}")

        if prefix:
            assert indent is not None
            depth: int = len(prefix) // len(indent)
            if prefix != indent * depth:
                mapping: Dict[str, str] = {" ": "<SPACE>", "\t": "<TAB>"}
                prefix_expanded = "".join(mapping[c] for c in prefix)
                indent_expanded = "".join(mapping[c] for c in indent)
                raise MacheteException(
                    f"{path}, line {index + 1}: "
                    f"invalid indent <b>{prefix_expanded}</b>, expected a multiply"
                    f" of <b>{indent_expanded}</b>. {hint}")
        else:
            depth = 0

        if depth > last_depth + 1:
            raise MacheteException(
                f"{path}, line {index + 1}: too much "
                f"indent (level {depth}, expected at most {last_depth + 1}) "
                f"for the branch <b>{branch}</b>. {hint}")
        last_depth = depth

        at_depth[depth] = branch
        parent = at_depth[depth - 1] if depth else None
        state.add_branch(branch, parent=parent, annotation=annotation)

    return state, indent


def render(state: MacheteState, indent: str) -> List[str]:
    """Return lines representing *state*, ready to join with newlines."""
    def render_dfs(branch: LocalBranchShortName, depth: int) -> List[str]:
        anno = state.get_annotation(branch)
        annotation = (" " + anno.unformatted_full_text) if anno is not None else ""
        result: List[str] = [depth * indent + branch + annotation]
        for child in (state.get_children(branch) or []):
            result += render_dfs(child, depth + 1)
        return result

    lines: List[str] = []
    for root in state.roots:
        lines += render_dfs(root, depth=0)
    return lines


def save(path: str, state: MacheteState, *, indent: str) -> None:
    """Write *state* to the branch layout file at *path*."""
    with open(path, "w") as f:
        f.write("\n".join(render(state, indent)) + "\n")
