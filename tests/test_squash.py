
import os
import sys

from tests.base_test import BaseTest
from tests.cli_runner import assert_failure, assert_success
from tests.git_repository import check_out, commit, create_repo, get_current_commit_hash, new_branch, set_git_config_key
from tests.mockers import fake_executables_on_path, fixed_author_and_committer_date_in_past, overridden_environment
from tests.shell import popen


class TestSquash(BaseTest):

    def test_squash_root_branch(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        commit()

        assert_failure(
            ["squash"],
            "git-machete cannot determine the range of commits unique to branch master.\n"
            "Use git machete squash --fork-point=... to select the commit after which the commits of master start.\n"
            "For example, if you want to squash 3 latest commits, use git machete squash --fork-point=HEAD~3."
        )

    def test_squash_no_commits(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")

        assert_failure(
            ["squash"],
            "No commits to squash. Use -f or --fork-point to specify the "
            "start of range of commits to squash."
        )

    def test_squash_single_commit(self) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch("master")
            commit("0")
            new_branch("develop")
            commit("1")

        assert_success(
            ["squash"],
            "Exactly one commit (e2e8daf) to squash, ignoring.\n"
            "Tip: use -f or --fork-point to specify where the range of commits to squash starts.\n"
        )

    def test_squash_with_valid_fork_point(self) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch('branch-0')
            commit("First commit.")
            commit("Second commit.")
            fork_point = get_current_commit_hash()

            with overridden_environment(GIT_AUTHOR_EMAIL="another@test.com"):
                commit("Third commit.")
            commit("Fourth commit.")

        with fixed_author_and_committer_date_in_past():
            assert_success(
                ['squash', '-f', fork_point],
                """
                Squashed 2 commits:

                    f441f1b Third commit.
                    85fbadf Fourth commit.

                To restore the original pre-squash commit, run:

                    git reset 85fbadfbf81551e6b7686e6fe2f44496847c76bf
                """
            )

        expected_branch_log = (
            "Third commit.\n"
            "Second commit.\n"
            "First commit."
        )

        current_branch_log = popen('git log -3 --format=%s')
        assert current_branch_log == expected_branch_log, \
            ("Verify that `git machete squash -f <fork-point>` squashes commit"
             " from one succeeding the fork-point until tip of the branch.")

        squash_commit_author = popen('git log -1 --format=%aE')
        assert squash_commit_author == "another@test.com"
        squash_commit_committer = popen('git log -1 --format=%cE')
        assert squash_commit_committer == "tester@test.com"

    def test_squash_with_invalid_fork_point(self) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch('branch-0')
            commit('0')
            new_branch('branch-1a')
            commit('1a')

            fork_point_to_branch_1a = get_current_commit_hash()

            check_out('branch-0')
            new_branch('branch-1b')
            commit('1b')

        assert_failure(
            ['squash', '-f', fork_point_to_branch_1a],
            "Fork point 0ba080756ab13b6b74266c8a5e376de5f5b8bb76 is not ancestor of or the tip of the branch-1b branch."
        )

    def test_squash_does_not_sign_when_commit_gpgsign_is_false(self) -> None:
        create_repo()
        new_branch("master")
        commit("0")
        new_branch("develop")
        commit("1")
        commit("2")

        marker = os.path.abspath("gpg-was-called")
        with fake_executables_on_path(gpg=_fake_gpg_body(marker)) as bin_dir:
            set_git_config_key("gpg.program", _gpg_program_path(bin_dir))
            _assert_squash_succeeds()
            assert not os.path.exists(marker)
            assert "gpgsig" not in popen("git cat-file -p HEAD")

    def test_squash_signs_when_commit_gpgsign_is_true(self) -> None:
        create_repo()
        new_branch("master")
        commit("0")
        new_branch("develop")
        commit("1")
        commit("2")

        marker = os.path.abspath("gpg-was-called")
        with fake_executables_on_path(gpg=_fake_gpg_body(marker)) as bin_dir:
            set_git_config_key("gpg.program", _gpg_program_path(bin_dir))
            set_git_config_key("commit.gpgsign", "true")
            _assert_squash_succeeds()
            assert os.path.exists(marker)
            assert "gpgsig" in popen("git cat-file -p HEAD")


def _gpg_program_path(bin_dir: str) -> str:
    name = "gpg.cmd" if sys.platform == "win32" else "gpg"
    return os.path.join(bin_dir, name).replace("\\", "/")


def _fake_gpg_body(marker_path: str) -> str:
    return f"""
import sys
open({marker_path!r}, "w").close()
sys.stderr.write("[GNUPG:] SIG_CREATED D 1EA99AD9 8 00 0 ABC\\n")
sys.stdout.write("-----BEGIN PGP SIGNATURE-----\\n\\ndummy\\n-----END PGP SIGNATURE-----\\n")
"""


def _assert_squash_succeeds() -> None:
    log_lines = popen("git log --reverse --format=%H:%h:%s master..HEAD").splitlines()
    last_full_hash, _, _ = log_lines[-1].split(":", 2)
    squashed_rows = "".join(
        f"    {short_hash} {subject}\n" for _, short_hash, subject in (line.split(":", 2) for line in log_lines))
    assert_success(
        ["squash"],
        f"Squashed {len(log_lines)} commits:\n\n"
        f"{squashed_rows}\n"
        f"To restore the original pre-squash commit, run:\n\n"
        f"    git reset {last_full_hash}\n"
    )
