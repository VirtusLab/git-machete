import pathlib
import re
from typing import Dict

import pytest

from tests.mockers import popen, rewrite_branch_layout_file
from tests.mockers_git_repository import (check_out, commit, create_repo,
                                          get_current_commit_hash, new_branch,
                                          set_git_config_key)

test_cases: Dict[str, str] = {
    "git machete ":
        "add advance anno completion delete-unmanaged diff discover edit file fork-point github gitlab "
        "go help is-managed list log reapply show slide-out squash status traverse update version",
    "git machete -":
        "--debug -h --help -v --verbose --version",
    "git machete a":
        "add advance anno",
    "git machete add ":
        "feature",
    "git machete add -":
        "-R --as-first-child --as-root --debug -f -h --help -o --onto -v --verbose -y --yes",
    "git machete add -o ":
        "develop master",
    "git machete add --onto ":
        "develop master",
    "git machete add --onto=":
        "develop master",
    "git machete advance -":
        "--debug -h --help -v --verbose -y --yes",
    "git machete anno -":
        "-H -L -b --branch --debug -h --help --sync-github-prs --sync-gitlab-mrs -v --verbose",
    "git machete anno -b ":
        "develop master",
    "git machete anno --branch ":
        "develop master",
    "git machete anno --branch=":
        "develop master",
    "git machete completion ":
        "bash fish zsh",
    "git machete delete-unmanaged -":
        "--debug -h --help -v --verbose -y --yes",
    "git machete d ":
        "develop feature master",
    "git machete diff ":
        "develop feature master",
    "git machete discover -":
        "-C --checked-out-since --debug -h --help -l --list-commits -r --roots -v --verbose -y --yes",
    "git machete e":
        "edit",
    "git machete f":
        "file fork-point",
    "git machete fork-point ":
        "develop feature master",
    "git machete fork-point -":
        "--debug -h --help --inferred --override-to --override-to-inferred --override-to-parent --unset-override -v --verbose",
    "git machete fork-point --inferred ":
        "develop feature master",
    "git machete fork-point --override-to=":
        "HEAD develop feature master",
    "git machete fork-point --unset-override ":
        "develop",
    "git machete github ":
        "anno-prs checkout-prs create-pr restack-pr retarget-pr update-pr-descriptions",
    "git machete github anno-prs -":
        "--debug -h --help -v --verbose --with-urls",
    "git machete github checkout-prs -":
        "--all --by --debug -h --help --mine -v --verbose",
    "git machete github create-pr -":
        "-U --debug --draft -h --help --title --update-related-descriptions -v --verbose --yes",
    "git machete github restack-pr -":
        "-U --debug -h --help --update-related-descriptions -v --verbose",
    "git machete github retarget-pr --":
        "--branch --debug --help --ignore-if-missing --update-related-descriptions --verbose",
    "git machete github retarget-pr -b ":
        "develop master",
    "git machete github update-pr-descriptions -":
        "--all --by --debug -h --help --mine --related -v --verbose",
    "git machete gitlab ":
        "anno-mrs checkout-mrs create-mr restack-mr retarget-mr update-mr-descriptions",
    "git machete gitlab anno-mrs -":
        "--debug -h --help -v --verbose --with-urls",
    "git machete gitlab checkout-mrs -":
        "--all --by --debug -h --help --mine -v --verbose",
    "git machete gitlab create-mr -":
        "-U --debug --draft -h --help --title --update-related-descriptions -v --verbose --yes",
    "git machete gitlab restack-mr -":
        "-U --debug -h --help --update-related-descriptions -v --verbose",
    "git machete gitlab retarget-mr --":
        "--branch --debug --help --ignore-if-missing --update-related-descriptions --verbose",
    "git machete gitlab retarget-mr -b ":
        "develop master",
    "git machete gitlab update-mr-descriptions -":
        "--all --by --debug -h --help --mine --related -v --verbose",
    "git machete g ":
        "down first last next prev root up",
    "git machete go ":
        "down first last next prev root up",
    "git machete help ":
        "add advance anno completion config delete-unmanaged diff discover edit file fork-point format github gitlab "
        "go help hooks is-managed list log reapply show slide-out squash status traverse update version",
    "git machete is-managed ":
        "develop feature master",
    "git machete list ":
        "addable childless managed slidable slidable-after unmanaged with-overridden-fork-point",
    "git machete l ":
        "develop feature master",
    "git machete log ":
        "develop feature master",
    "git machete reapply -":
        "--debug -f --fork-point -h --help -v --verbose",
    "git machete reapply --fork-point ":
        "HEAD develop feature master",
    "git machete s -":
        "-L --color --debug -h --help -l --list-commits --list-commits-with-hashes --no-detect-squash-merges -v --verbose",
    "git machete show ":
        "current down first last next prev root up",
    "git machete slide-out ":
        "develop",
    "git machete slide-out -":
        "-M -d --debug --delete --down-fork-point -h --help --merge -n "
        "--no-edit-merge --no-interactive-rebase --removed-from-remote -v --verbose",
    "git machete slide-out --down-fork-point=":
        "HEAD develop feature master",
    "git machete squash -":
        "--debug -f --fork-point -h --help -v --verbose",
    "git machete squash --fork-point ":
        "HEAD develop feature master",
    "git machete squash --fork-point=":
        "HEAD develop feature master",
    "git machete status -":
        "-L --color --debug -h --help -l --list-commits --list-commits-with-hashes --no-detect-squash-merges -v --verbose",
    "git machete status --color ":
        "always auto never",
    "git machete status --color=":
        "always auto never",
    "git machete t -":
        "-F -H -L -M -W --debug --fetch -h --help -l --list-commits --merge "
        "-n --no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push --no-push-untracked --push --push-untracked --return-to --start-from "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    "git machete traverse -":
        "-F -H -L -M -W --debug --fetch -h --help -l --list-commits --merge "
        "-n --no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push --no-push-untracked --push --push-untracked --return-to --start-from "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    "git machete traverse --start-from ":
        "first-root here root",
    "git machete traverse --start-from=":
        "first-root here root",
    "git machete traverse --return-to ":
        "here nearest-remaining stay",
    "git machete traverse --return-to=":
        "here nearest-remaining stay",
    "git machete update -":
        "-M --debug -f --fork-point -h --help --merge -n --no-edit-merge --no-interactive-rebase -v --verbose",
    "git machete update -f ":
        "HEAD develop feature master",
    "git machete version ":
        ""
}


@pytest.mark.completion_e2e
class TestCompletionEndToEnd:

    create_repo()

    @classmethod
    def setup_class(cls) -> None:
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        set_git_config_key("machete.overrideForkPoint.develop.to", get_current_commit_hash())
        commit()
        new_branch("feature")
        commit()
        check_out("master")
        rewrite_branch_layout_file("master\n\tdevelop")

    def test_fish_version(self) -> None:
        raw = popen("fish --version")
        version_match = re.search(r"[0-9]+(\.[0-9]+)*", raw)
        assert version_match is not None
        version_raw = version_match.group(0)
        version = tuple(map(int, version_raw.split('.')))

        assert version >= (4, 0, 2), f"Fish version installed in the system must be at least 4.0.2 (is: {version_raw})"

    @pytest.mark.parametrize("input,expected_result", test_cases.items(), ids=lambda x: x if x.startswith('git machete') else '')
    @pytest.mark.parametrize("script_name", ["complete-bash.sh", "complete-fish.fish", "complete-zsh.zsh"])
    def test_completion(self, input: str, expected_result: str, script_name: str) -> None:
        script = pathlib.Path(__file__).parent.joinpath(script_name).absolute()
        output_tokens = popen(f"'{script}' '{input}'").split()
        result = " ".join(sorted(output_tokens, key=lambda s: ''.join([c for c in s if c.isalpha()])))
        assert result == expected_result, f"for '{input}'"
