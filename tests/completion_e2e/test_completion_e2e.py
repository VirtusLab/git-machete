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
    # Mutex: with --as-root on the cmdline,
    # `-f`/`--as-first-child` and `-o`/`--onto` MUST NOT be suggested.
    "git machete add --as-root -":
        "--debug -h --help -v --verbose -y --yes",
    # Mutex: with --as-root and -f (== --as-first-child) on the cmdline,
    # `-o`/`--onto` MUST NOT be suggested (mutex with --as-root).
    "git machete add --as-root -f -":
        "--debug -h --help -v --verbose -y --yes",
    # Same mutex case as above, expressed with short flags `-R -f`;
    # `-o`/`--onto` MUST NOT be suggested.
    "git machete add -R -f -":
        "--debug -h --help -v --verbose -y --yes",
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
    # Mutex: with --sync-github-prs (== -H) on the cmdline,
    # `-L`/`--sync-gitlab-mrs` MUST NOT be suggested.
    "git machete anno --sync-github-prs -":
        "-b --branch --debug -h --help -v --verbose",
    # Mutex: with --sync-gitlab-mrs (== -L) on the cmdline,
    # `-H`/`--sync-github-prs` MUST NOT be suggested.
    "git machete anno --sync-gitlab-mrs -":
        "-b --branch --debug -h --help -v --verbose",
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
    # Mutex: with --inferred on the cmdline,
    # `--override-to=`, `--override-to-parent`, `--override-to-inferred`,
    # `--unset-override` MUST NOT be suggested.
    "git machete fork-point --inferred -":
        "--debug -h --help -v --verbose",
    # Mutex: with --override-to-parent on the cmdline,
    # `--inferred`, `--override-to=`, `--override-to-inferred`,
    # `--unset-override` MUST NOT be suggested.
    "git machete fork-point --override-to-parent -":
        "--debug -h --help -v --verbose",
    # Mutex: with --override-to-inferred on the cmdline,
    # `--inferred`, `--override-to=`, `--override-to-parent`,
    # `--unset-override` MUST NOT be suggested.
    "git machete fork-point --override-to-inferred -":
        "--debug -h --help -v --verbose",
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
        "-U --debug --draft -h --help --title --update-related-descriptions -v --verbose -y --yes",
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
        "-U --debug --draft -h --help --title --update-related-descriptions -v --verbose -y --yes",
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
        "develop master",
    "git machete slide-out -":
        "-M -d --debug --delete --down-fork-point -h --help --merge -n "
        "--no-edit-merge --no-interactive-rebase --no-rebase --removed-from-remote -v --verbose",
    "git machete slide-out --down-fork-point=":
        "HEAD develop feature master",
    # Mutex: with --merge on the cmdline, `-d`/`--down-fork-point=`,
    # `--no-rebase`, `--no-interactive-rebase`, `--removed-from-remote`
    # MUST NOT be suggested.
    "git machete slide-out --merge -":
        "--debug --delete -h --help -n --no-edit-merge -v --verbose",
    # Same mutex case as above, expressed with the short flag `-M`.
    "git machete slide-out -M -":
        "--debug --delete -h --help -n --no-edit-merge -v --verbose",
    # Mutex: with -n on the cmdline,
    # `--no-edit-merge`, `--no-interactive-rebase`, `--removed-from-remote`
    # MUST NOT be suggested.
    "git machete slide-out -n -":
        "-M -d --debug --delete --down-fork-point -h --help --merge --no-rebase -v --verbose",
    # Mutex: with --no-rebase on the cmdline,
    # `-d`/`--down-fork-point=`, `-M`/`--merge`, `--no-edit-merge`,
    # `--no-interactive-rebase`, `--removed-from-remote`
    # MUST NOT be suggested.
    "git machete slide-out --no-rebase -":
        "--debug --delete -h --help -n -v --verbose",
    # Mutex: with --removed-from-remote on the cmdline,
    # `-d`/`--down-fork-point=`, `-M`/`--merge`, `-n`, `--no-edit-merge`,
    # `--no-interactive-rebase`, `--no-rebase` MUST NOT be suggested
    # (only `--delete` is compatible with --removed-from-remote).
    "git machete slide-out --removed-from-remote -":
        "--debug --delete -h --help -v --verbose",
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
        "--no-push --no-push-untracked --push --push-untracked --return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    "git machete t --return-to ":
        "HERE NEAREST-REMAINING STAY",
    "git machete t --return-to=":
        "HERE NEAREST-REMAINING STAY",
    "git machete t --start-from ":
        "FIRST-ROOT HERE ROOT develop feature master",
    "git machete t --start-from=":
        "FIRST-ROOT HERE ROOT develop feature master",
    "git machete traverse -":
        "-F -H -L -M -W --debug --fetch -h --help -l --list-commits --merge "
        "-n --no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push --no-push-untracked --push --push-untracked --return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    "git machete traverse --return-to ":
        "HERE NEAREST-REMAINING STAY",
    "git machete traverse --return-to=":
        "HERE NEAREST-REMAINING STAY",
    "git machete traverse --start-from ":
        "FIRST-ROOT HERE ROOT develop feature master",
    "git machete traverse --stop-after ":
        "develop feature master",
    "git machete traverse --stop-after=":
        "develop feature master",
    # Mutex: with --push on the cmdline, `--no-push` MUST NOT be suggested.
    "git machete traverse --push -":
        "-F -H -L -M -W --debug --fetch -h --help -l --list-commits --merge "
        "-n --no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push-untracked --push-untracked --return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    # Mutex: with --no-push on the cmdline, `--push` MUST NOT be suggested.
    "git machete traverse --no-push -":
        "-F -H -L -M -W --debug --fetch -h --help -l --list-commits --merge "
        "-n --no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push-untracked --push-untracked --return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    # Mutex: with --push-untracked on the cmdline,
    # `--no-push-untracked` MUST NOT be suggested.
    "git machete traverse --push-untracked -":
        "-F -H -L -M -W --debug --fetch -h --help -l --list-commits --merge "
        "-n --no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push --push --return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    # Mutex: with --no-push-untracked on the cmdline,
    # `--push-untracked` MUST NOT be suggested.
    "git machete traverse --no-push-untracked -":
        "-F -H -L -M -W --debug --fetch -h --help -l --list-commits --merge "
        "-n --no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push --push --return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    # Mutex: with -W (== --fetch + --whole) on the cmdline,
    # `-F`/`--fetch`, `-l`/`--list-commits`, `-w`/`--whole` MUST NOT be suggested.
    "git machete traverse -W -":
        "-H -L -M --debug -h --help --merge -n --no-detect-squash-merges "
        "--no-edit-merge --no-interactive-rebase --no-push --no-push-untracked "
        "--push --push-untracked --return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -y --yes",
    # Mutex: with -F (== --fetch) on the cmdline, `-W` MUST NOT be suggested
    # (since -W implies --fetch + --whole).
    "git machete traverse -F -":
        "-H -L -M --debug -h --help -l --list-commits --merge -n "
        "--no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push --no-push-untracked --push --push-untracked "
        "--return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    # Mutex: with -H (== --sync-github-prs) on the cmdline,
    # `-L`/`--sync-gitlab-mrs` MUST NOT be suggested.
    "git machete traverse -H -":
        "-F -M -W --debug --fetch -h --help -l --list-commits --merge -n "
        "--no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push --no-push-untracked --push --push-untracked "
        "--return-to --start-from --stop-after -v --verbose -w --whole -y --yes",
    # Mutex: with -M (== --merge) on the cmdline,
    # `--no-interactive-rebase` MUST NOT be suggested.
    "git machete traverse -M -":
        "-F -H -L -W --debug --fetch -h --help -l --list-commits -n "
        "--no-detect-squash-merges --no-edit-merge "
        "--no-push --no-push-untracked --push --push-untracked "
        "--return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    # Mutex: with -n on the cmdline,
    # `--no-edit-merge`, `--no-interactive-rebase`, `-y`/`--yes` MUST NOT be suggested.
    "git machete traverse -n -":
        "-F -H -L -M -W --debug --fetch -h --help -l --list-commits --merge "
        "--no-detect-squash-merges "
        "--no-push --no-push-untracked --push --push-untracked "
        "--return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole",
    # Mutex: with --no-interactive-rebase on the cmdline,
    # `-n` and `-M`/`--merge` MUST NOT be suggested.
    "git machete traverse --no-interactive-rebase -":
        "-F -H -L -W --debug --fetch -h --help -l --list-commits "
        "--no-detect-squash-merges --no-edit-merge "
        "--no-push --no-push-untracked --push --push-untracked "
        "--return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole -y --yes",
    # Mutex: with -y (== --yes) on the cmdline, `-n` MUST NOT be suggested
    # (since --yes implies -n).
    "git machete traverse -y -":
        "-F -H -L -M -W --debug --fetch -h --help -l --list-commits --merge "
        "--no-detect-squash-merges --no-edit-merge --no-interactive-rebase "
        "--no-push --no-push-untracked --push --push-untracked "
        "--return-to --start-from --stop-after "
        "--sync-github-prs --sync-gitlab-mrs -v --verbose -w --whole",
    "git machete update -":
        "-M --debug -f --fork-point -h --help --merge -n --no-edit-merge --no-interactive-rebase -v --verbose",
    "git machete update -f ":
        "HEAD develop feature master",
    # Mutex: with -n on the cmdline,
    # `--no-edit-merge` and `--no-interactive-rebase` MUST NOT be suggested.
    "git machete update -n -":
        "-M --debug -f --fork-point -h --help --merge -v --verbose",
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
