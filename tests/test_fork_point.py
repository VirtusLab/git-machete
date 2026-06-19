import os

from pytest_mock import MockerFixture

from git_machete.utils.terminal import FullTerminalAnsiOutputCodes
from tests.base_test import BaseTest
from tests.cli_runner import assert_failure, assert_success, launch_command, rewrite_branch_layout_file
from tests.git_repository import (add_remote, check_out, commit, create_repo, create_repo_with_remote, delete_branch, fetch,
                                  get_commit_hash, get_current_commit_hash, merge, new_branch, new_orphan_branch, pull, push, reset_to,
                                  set_git_config_key)
from tests.mockers import fixed_author_and_committer_date_in_past
from tests.shell import execute, remove_directory


class TestForkPoint(BaseTest):

    def test_fork_point_get(self) -> None:
        with fixed_author_and_committer_date_in_past():
            create_repo()
            new_branch("master")
            commit(message="master commit.")
            new_branch("develop")
            commit(message="develop commit.")
            new_branch("feature")
            commit('feature commit.')

        body: str = \
            """
            master
            develop
                feature
            """
        rewrite_branch_layout_file(body)

        # Test `git machete fork-point` without providing the branch name
        # hash 22a73eb0478439391949c6d544938a8aeee684c5 corresponds to the commit on develop branch
        assert_success(["fork-point"], "22a73eb0478439391949c6d544938a8aeee684c5\n")
        assert_success(["fork-point", "--inferred"], "22a73eb0478439391949c6d544938a8aeee684c5\n")

        # hash 3ce566089cda4d3303309cf93883ab75f531c855 corresponds to the commit on master branch
        assert_success(["fork-point", 'develop'], "3ce566089cda4d3303309cf93883ab75f531c855\n")

        assert_success(["fork-point", 'refs/heads/develop'], "3ce566089cda4d3303309cf93883ab75f531c855\n")

    def test_fork_point_explain(self) -> None:
        with fixed_author_and_committer_date_in_past():
            create_repo()
            new_branch("master")
            commit(message="master commit.")
            new_branch("develop")
            commit(message="develop commit.")
            new_branch("feature")
            commit('feature commit.')

        rewrite_branch_layout_file("""
            master
            develop
                feature
            """)

        # The fork point of `feature` is the tip of `develop`; `--explain`
        # mirrors the `-> fork point ???` wording from `status -l` to spell
        # out which branches the algorithm inferred the fork point from.
        # The hash goes to stdout, the explanation to stderr (the test
        # helper merges both streams in order).
        assert_success(
            ["fork-point", "feature", "--explain"],
            "22a73eb0478439391949c6d544938a8aeee684c5\n"
            "this commit seems to be a part of the unique history of develop\n"
        )

        # Fork point of `develop` is the tip of `master`.
        assert_success(
            ["fork-point", "develop", "--explain"],
            "3ce566089cda4d3303309cf93883ab75f531c855\n"
            "this commit seems to be a part of the unique history of master\n"
        )

        # `--inferred --explain` combination is allowed.
        assert_success(
            ["fork-point", "feature", "--inferred", "--explain"],
            "22a73eb0478439391949c6d544938a8aeee684c5\n"
            "this commit seems to be a part of the unique history of develop\n"
        )

        # When an override is active, `--explain` (without `--inferred`)
        # surfaces the override rather than running the inference: the user
        # gets a clear "this came from the override" signal instead of being
        # silently shown reflog-derived branches that don't actually drive
        # the answer.
        launch_command("fork-point", "feature", "--override-to-parent")
        assert_success(
            ["fork-point", "feature", "--explain"],
            "22a73eb0478439391949c6d544938a8aeee684c5\n"
            "fork point of feature is overridden\n"
        )

        # `--inferred --explain` ignores the override and explains the
        # inferred fork point regardless. Here the override happens to point
        # at the same commit (parent's tip) that inference would land on, so
        # the hash is unchanged - but the explanation now reports the
        # branches the inference ran against, not the override.
        assert_success(
            ["fork-point", "feature", "--inferred", "--explain"],
            "22a73eb0478439391949c6d544938a8aeee684c5\n"
            "this commit seems to be a part of the unique history of develop\n"
        )

        # Combining with override-* / --unset-override is rejected.
        assert_failure(
            ["fork-point", "feature", "--override-to-parent", "--explain"],
            "--explain cannot be combined with "
            "--override-to/--override-to-inferred/--override-to-parent/--unset-override."
        )

    def test_fork_point_explain_dedups_inferring_branches(self) -> None:
        # When a single commit appears multiple times in a branch's
        # *filtered* reflog (e.g. after two consecutive ff-merges/pulls
        # to the same upstream tip), `__match_log_to_filtered_reflogs`
        # used to record `BranchPair(master, master)` once per
        # occurrence. The explanation then read
        # "...part of the unique history of master and master", which
        # is meaningless to the user and misleading in the debug logs.
        # The fix dedups branch pairs per hash at computation time, so
        # `master` is listed exactly once regardless of how many reflog
        # events on `master` happen to point at the fork point.
        with fixed_author_and_committer_date_in_past():
            create_repo()
            new_branch("master")
            commit("master initial")
            new_branch("sidebranch")
            commit("sidebranch commit")
            sidebranch_tip = get_current_commit_hash()
            check_out("master")
            # First ff-merge: master moves to `sidebranch_tip`; reflog
            # gets a "merge sidebranch: Fast-forward" entry whose new
            # value is `sidebranch_tip`. This subject is not excluded
            # by `filtered_reflog`.
            merge("sidebranch")
            # Branch develop off the new master tip so develop's fork
            # point lands at `sidebranch_tip`.
            new_branch("develop")
            commit("develop commit")
            check_out("master")
            # Rewind master and ff-merge sidebranch again, so master's
            # filtered reflog ends up with two non-excluded entries
            # both pointing at `sidebranch_tip`.
            reset_to("master~1")
            merge("sidebranch")
            # Drop `sidebranch` so it doesn't contribute its own
            # `BranchPair(sidebranch, sidebranch)` to the inferring set
            # - the case under test is specifically about a single
            # branch (`master`) being listed multiple times.
            delete_branch("sidebranch")

        rewrite_branch_layout_file("""
            master
                develop
            """)

        # Without the dedup the explanation read
        #   "...part of the unique history of master and master"
        # because `BranchPair(master, master)` was appended twice.
        assert_success(
            ["fork-point", "develop", "--explain"],
            f"{sidebranch_tip}\n"
            "this commit seems to be a part of the unique history of master\n"
        )

    def test_fork_point_override_for_invalid_branch(self) -> None:
        create_repo()
        new_branch("master")
        commit()

        assert_failure(
            ["fork-point", "--override-to=@", "no-such-branch"],
            "no-such-branch is not a local branch"
        )

    def test_fork_point_override_to_non_ancestor_commit(self) -> None:
        with fixed_author_and_committer_date_in_past():
            create_repo()
            new_branch("master")
            commit("0")
            new_branch("develop")
            commit("1")
            check_out("master")
            commit("2")

        assert_failure(
            ["fork-point", "develop", "--override-to=master"],
            "Cannot override fork point: master (commit 70c61fe) is not an ancestor of develop"
        )

    def test_fork_point_override_to_commit(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        master_branch_first_commit_hash = get_current_commit_hash()
        commit("master second commit")
        develop_branch_fork_point = get_current_commit_hash()
        new_branch("develop")
        commit("develop commit")

        body: str = \
            """
            master
            develop
            """
        rewrite_branch_layout_file(body)

        # invalid fork point with length not equal to 40
        set_git_config_key('machete.overrideForkPoint.develop.to', 39 * 'a')
        assert launch_command('fork-point').strip() == develop_branch_fork_point

        # invalid, non-hexadecimal alphanumeric characters present in the fork point
        set_git_config_key('machete.overrideForkPoint.develop.to', 20 * 'g1')
        assert launch_command('fork-point').strip() == develop_branch_fork_point

        # invalid, non-hexadecimal special characters present in the fork point
        set_git_config_key('machete.overrideForkPoint.develop.to', 40 * '#')
        assert launch_command('fork-point').strip() == develop_branch_fork_point

        # invalid fork-point override revision
        assert_failure(['fork-point', '--override-to=no-such-commit'], "Cannot find revision no-such-commit")

        # valid commit hash but not present in the repository
        set_git_config_key('machete.overrideForkPoint.develop.to', 40 * 'a')
        assert launch_command('fork-point').strip() == (
               "Warn: since branch develop is no longer a descendant of commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, the fork point override to this commit no longer applies.\n"  # noqa: E501
               "Consider running:\n"
               "  git machete fork-point --unset-override develop\n\n" +
               develop_branch_fork_point)

        # valid fork-point override commit hash
        launch_command('fork-point', f'--override-to={master_branch_first_commit_hash}')
        assert launch_command('fork-point').strip() == master_branch_first_commit_hash
        assert launch_command('fork-point', '--inferred').strip() == develop_branch_fork_point

        launch_command('fork-point', '--unset-override')
        assert launch_command('fork-point').strip() == develop_branch_fork_point
        assert launch_command('fork-point', '--inferred').strip() == develop_branch_fork_point

        assert_success(['fork-point', '--unset-override'], "")

    def test_fork_point_override_to_parent_and_inferred(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, "git_machete.utils.terminal.is_terminal_fully_fledged", lambda: True)

        with fixed_author_and_committer_date_in_past():
            create_repo_with_remote()
            new_branch("master")
            commit("master  commit")
            new_branch("in-between")
            commit("in-between commit")
            new_branch("develop")
            commit("develop commit")

        body: str = \
            """
            master
                develop
            """
        rewrite_branch_layout_file(body)

        assert launch_command("fork-point").strip() == "ad97c343b69296e96858058d8d668cca0132402a"
        assert launch_command("fork-point", "--inferred").strip() == "ad97c343b69296e96858058d8d668cca0132402a"
        assert_success(
            ["status", "--list-commits-with-hashes"],
            """
              master (untracked)
              |
              | ad97c34  in-between commit -> fork point ??? this commit seems to be a part of the unique history of in-between
              | 989bd92  develop commit
              ?-develop * (untracked)

            Warn: yellow edge indicates that fork point for develop is probably incorrectly inferred,
            or that some extra branch should be between master and develop.

            Consider using git machete fork-point develop --override-to-parent,
            rebasing develop onto its parent with git machete update,
            or reattaching develop under a different parent branch.
            """
        )

        assert_success(
            ["fork-point", "--override-to-parent"],
            """
            Fork point for develop is overridden to master (commit 81504c0).
            This applies as long as develop points to commit 81504c0 or its descendant.
            """
        )
        assert launch_command("fork-point").strip() == "81504c0efc45763333d3a6f884e5d3a97d8f4c40"
        assert launch_command("fork-point", "--inferred").strip() == "ad97c343b69296e96858058d8d668cca0132402a"
        assert_success(
            ["status", "-L"],
            """
              master (untracked)
              |
              | ad97c34  in-between commit
              | 989bd92  develop commit
              o-develop * (untracked)
            """
        )

        assert_failure(["fork-point", "--override-to-parent", "master"], "Branch master does not have upstream (parent) branch")

        assert_success(
            ["fork-point", "--override-to-inferred"],
            """
            Fork point for develop is overridden to commit ad97c34.
            This applies as long as develop points to commit ad97c34 or its descendant.

            Warn: git machete fork-point --override-to-inferred may lead to a confusing user experience and is deprecated.

            If the commits between master (parent of develop) and inferred commit ad97c34 do NOT belong to develop, consider using:
                git checkout develop
                git machete update --fork-point="ad97c343b69296e96858058d8d668cca0132402a"

            Otherwise, if you're okay with treating these commits as a part of develop's unique history, use instead:
                git machete fork-point develop --override-to-parent
            """
        )
        assert launch_command("fork-point").strip() == "ad97c343b69296e96858058d8d668cca0132402a"
        assert launch_command("fork-point", "--inferred").strip() == "ad97c343b69296e96858058d8d668cca0132402a"
        assert_success(
            ["status", "-L"],
            """
              master (untracked)
              |
              | ad97c34  in-between commit -> fork point: overridden
              | 989bd92  develop commit
              o-develop * (untracked)
            """
        )

        # Validate the full ANSI rendering of the green `-> fork point: overridden` annotation:
        # the arrow must be the non-ASCII `\u279a`, the marker must be RED, and the
        # `: overridden` suffix must stay outside the red span.
        E = FullTerminalAnsiOutputCodes
        raw_output = launch_command("status", "-L", "--color=always")
        expected_ansi = (
            f"  {E.BOLD}master{E.ENDC_BOLD_DIM}{E.ORANGE} (untracked){E.ENDC}\n"
            f"  {E.GREEN}│{E.ENDC}\n"
            f"  {E.GREEN}│{E.ENDC} {E.DIM}ad97c34{E.ENDC_BOLD_DIM}  {E.DIM}in-between commit{E.ENDC_BOLD_DIM} "
            f"{E.RED}➔ fork point{E.ENDC}: overridden\n"
            f"  {E.GREEN}│{E.ENDC} {E.DIM}989bd92{E.ENDC_BOLD_DIM}  {E.DIM}develop commit{E.ENDC_BOLD_DIM}\n"
            f"  {E.GREEN}└─{E.ENDC}{E.BOLD}{E.UNDERLINE}develop{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}"
            f"{E.ORANGE} (untracked){E.ENDC}\n"
        )
        assert raw_output == expected_ansi

    def test_fork_point_override_marker_in_status(self) -> None:
        # When fork point is overridden to a non-trivial commit (not at the parent's tip),
        # `status -l` should still classify the edge as green and annotate the overridden
        # fork-point commit with `-> fork point: overridden`.
        with fixed_author_and_committer_date_in_past():
            create_repo()
            new_branch("master")
            commit("master commit")
            new_branch("develop")
            commit("first develop commit")
            first_develop_commit = get_current_commit_hash()
            commit("second develop commit")
            commit("third develop commit")

        body: str = \
            """
            master
                develop
            """
        rewrite_branch_layout_file(body)

        launch_command("fork-point", f"--override-to={first_develop_commit}")
        assert launch_command("fork-point").strip() == first_develop_commit

        assert_success(
            ["status", "-l"],
            """
            master
            |
            | first develop commit -> fork point: overridden
            | second develop commit
            | third develop commit
            o-develop *
            """
        )

    def test_fork_point_overridden_to_non_descendant_of_parent_while_branch_descendant_of_parent(self) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch("branch-0")
            commit("0")
            new_branch("branch-1")
            commit("1")
            new_branch("branch-2")
            commit("2")

        body: str = \
            """
            branch-1
                branch-2
            """
        rewrite_branch_layout_file(body)
        assert_success(
            ['fork-point', '--override-to=5e35f5b'],
            """
            Fork point for branch-2 is overridden to commit 5e35f5b.
            This applies as long as branch-2 points to commit 5e35f5b or its descendant.

            Warn: git machete fork-point --override-to=... may lead to a confusing user experience and is deprecated.

            If the commits between branch-1 (parent of branch-2) and selected commit 5e35f5b do NOT belong to branch-2, consider using:
                git checkout branch-2
                git machete update --fork-point="5e35f5b"

            Otherwise, if you're okay with treating these commits as a part of branch-2's unique history, use instead:
                git machete fork-point branch-2 --override-to-parent
            """
        )

        assert launch_command("fork-point").strip() == get_commit_hash("branch-1")

    def test_fork_point_while_parent_unrelated_to_child(self) -> None:
        create_repo()
        new_branch("branch-1")
        commit()
        new_orphan_branch("branch-2")
        commit()

        body: str = \
            """
            branch-1
                branch-2
            """
        rewrite_branch_layout_file(body)

        assert_failure(
            ["fork-point"],
            "Fork point not found for branch branch-2; use git machete fork-point branch-2 --override-to..."
        )

    def test_fork_point_when_no_other_branches(self) -> None:
        create_repo()
        new_branch("branch-1")
        commit()

        assert_failure(
            ["fork-point"],
            "Fork point not found for branch branch-1; use git machete fork-point branch-1 --override-to..."
        )

    def test_fork_point_for_non_existent_branch(self) -> None:
        create_repo()
        assert_failure(
            ["fork-point", "no-such-branch"],
            "no-such-branch is not a local branch"
        )

    def test_fork_point_covering_reflog_of_remote_branch(self) -> None:
        (local_path, remote_path) = create_repo_with_remote()
        with fixed_author_and_committer_date_in_past():
            new_branch("master")
            commit('some commit')
            push()

            new_branch("develop")
            commit("fork-point commit")
            push()  # commit dab0e28

            os.chdir(remote_path)
            execute("git update-ref refs/heads/master develop")
            os.chdir(local_path)
            check_out("master")
            pull()
            check_out("develop")

        assert_success(
            ["fork-point"],
            "dab0e2883ab0445f2add2bdd6329870d9d795e05\n"
        )

        # Let's remove reflogs for local branches.
        # Fork point should be inferred based on reflog of origin/master.
        remove_directory(".git/logs/refs/heads/")
        assert_success(
            ["fork-point"],
            "dab0e2883ab0445f2add2bdd6329870d9d795e05\n"
        )

    def test_fork_point_reachable_from_master_but_not_on_its_reflog(self) -> None:
        (local_path, remote_path) = create_repo_with_remote()
        other_local_path = create_repo("other-local", bare=False, switch_dir_to_new_repo=False)

        with fixed_author_and_committer_date_in_past():
            new_branch("master")
            commit()
            push()

            first_master_commit = get_current_commit_hash()
            os.chdir(other_local_path)
            add_remote("origin", remote_path)
            fetch()
            check_out("master")
            commit()
            push()

            second_master_commit = get_current_commit_hash()
            new_branch("feature")
            commit()
            push()
            check_out("master")
            commit()
            push()

            os.chdir(local_path)
            check_out("master")
            pull()
            check_out("feature")

        assert_success(
            ["fork-point"],
            second_master_commit + "\n"
        )

        # This is an unlikely scenario, devised to cover the case
        # when there's no merge base between `feature` branch and a branch containing its un-improved fork point.
        with fixed_author_and_committer_date_in_past():
            new_orphan_branch("develop")
            commit()
            check_out("master")
            reset_to("develop")
            check_out("feature")

        assert_success(
            ["fork-point"],
            first_master_commit + "\n"
        )

    def test_fork_point_fallback_to_parent(self) -> None:
        create_repo_with_remote()
        new_branch("master")
        commit()
        push()

        new_branch("develop")
        commit()
        push()
        delete_branch("master")
        check_out("master")  # out of remote branch

        rewrite_branch_layout_file("master\n\tdevelop")
        master_commit = get_commit_hash("master")
        develop_fork_point = launch_command("fork-point", "develop").rstrip()
        assert develop_fork_point == master_commit
