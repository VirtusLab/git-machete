import os

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, execute,
                      fixed_author_and_committer_date_in_past, launch_command,
                      remove_directory, rewrite_branch_layout_file)
from .mockers_git_repository import (add_remote, check_out, commit,
                                     create_repo, create_repo_with_remote,
                                     delete_branch, fetch, get_commit_hash,
                                     get_current_commit_hash, new_branch,
                                     new_orphan_branch, pull, push, reset_to,
                                     set_git_config_key)


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

    def test_fork_point_override_to_parent_and_inferred(self) -> None:
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

            Consider using git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent develop,
            or reattaching develop under a different parent branch.
            """
        )

        launch_command("fork-point", "--override-to-parent")
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

        launch_command("fork-point", "--override-to-inferred")
        assert launch_command("fork-point").strip() == "ad97c343b69296e96858058d8d668cca0132402a"
        assert launch_command("fork-point", "--inferred").strip() == "ad97c343b69296e96858058d8d668cca0132402a"
        assert_success(
            ["status", "-L"],
            """
              master (untracked)
              |
              | 989bd92  develop commit
              o-develop * (untracked)
            """
        )

    def test_fork_point_overridden_to_non_descendant_of_parent_while_branch_descendant_of_parent(self) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch("branch-0")
            commit()
            new_branch("branch-1")
            commit()
            new_branch("branch-2")
            commit()

        body: str = \
            """
            branch-1
                branch-2
            """
        rewrite_branch_layout_file(body)
        launch_command('fork-point', '--override-to=branch-0')

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
