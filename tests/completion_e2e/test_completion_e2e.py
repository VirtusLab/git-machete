import pathlib
from typing import Dict

import pytest

from tests.base_test import GitRepositorySandbox
from tests.mockers import rewrite_branch_layout_file

test_cases: Dict[str, str] = {
    "git machete ":
        "add advance anno completion delete-unmanaged diff discover edit file fork-point github go "
        "help is-managed list log reapply show slide-out squash status traverse update version",
    "git machete -":
        "--debug -h --help -v --verbose --version",
    "git machete a":
        "add advance anno",
    "git machete add ":
        "feature",
    "git machete add -o ":
        "develop master",
    "git machete add --onto ":
        "develop master",
    "git machete add --onto=":
        "develop master",
    "git machete advance -":
        "--debug -h --help -v --verbose -y --yes",
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
        "anno-prs checkout-prs create-pr restack-pr retarget-pr",
    "git machete github anno-prs -":
        "--debug -h --help -v --verbose --with-urls",
    "git machete github checkout-prs -":
        "--all --by --debug -h --help --mine -v --verbose",
    "git machete github create-pr -":
        "--debug --draft -h --help --title -v --verbose --yes",
    "git machete github retarget-pr --":
        "--branch --debug --help --ignore-if-missing --verbose",
    "git machete github retarget-pr -b ":
        "develop master",
    "git machete g ":
        "down first last next prev root up",
    "git machete go ":
        "down first last next prev root up",
    "git machete help ":
        "add advance anno completion config delete-unmanaged diff discover edit file fork-point format github go "
        "help hooks is-managed list log reapply show slide-out squash status traverse update version",
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
    "git machete squash --fork-point=":
        "HEAD develop feature master",
    "git machete status -":
        "-L --color --debug -h --help -l --list-commits --list-commits-with-hashes --no-detect-squash-merges -v --verbose",
    "git machete status --color=":
        "always auto never",
    "git machete t -":
        "-F -M -W --debug --fetch -h --help -l --list-commits --merge -n --no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push --no-push-untracked --push --push-untracked --return-to --start-from -v --verbose -w --whole -y --yes",
    "git machete traverse -":
        "-F -M -W --debug --fetch -h --help -l --list-commits --merge -n --no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push --no-push-untracked --push --push-untracked --return-to --start-from -v --verbose -w --whole -y --yes",
    "git machete update -":
        "-M --debug -f --fork-point -h --help --merge -n --no-edit-merge --no-interactive-rebase -v --verbose",
    "git machete update -f ":
        "HEAD develop feature master",
    "git machete version ":
        ""
}


@pytest.mark.completion_e2e
class TestCompletionEndToEnd:

    repo_sandbox = GitRepositorySandbox()

    @classmethod
    def setup_class(cls) -> None:
        (
            cls.repo_sandbox
            # Create the remote and sandbox repos, chdir into sandbox repo
            .new_repo(cls.repo_sandbox.remote_path, bare=True)
            .new_repo(cls.repo_sandbox.local_path, bare=False)
            .add_remote("origin", cls.repo_sandbox.remote_path)
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .commit()
            .set_git_config_key("machete.overrideForkPoint.develop.to", cls.repo_sandbox.get_current_commit_hash())
            .commit()
            .new_branch("feature")
            .commit()
            .check_out("master")
        )
        rewrite_branch_layout_file("master\n\tdevelop")

    @pytest.mark.parametrize("input,expected_result", test_cases.items(), ids=lambda x: x if x.startswith('git machete') else '')
    @pytest.mark.parametrize("script_name", ["complete-bash.sh", "complete-fish.fish", "complete-zsh.zsh"])
    def test_completion(self, input: str, expected_result: str, script_name: str) -> None:
        script = pathlib.Path(__file__).parent.joinpath(script_name).absolute()
        output_tokens = self.repo_sandbox.popen(f"'{script}' '{input}'").split()
        result = " ".join(sorted(output_tokens, key=lambda s: ''.join([c for c in s if c.isalpha()])))
        assert result == expected_result, f"for '{input}'"
