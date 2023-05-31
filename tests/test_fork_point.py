
from .base_test import BaseTest
from .mockers import (assert_failure, assert_success,
                      fixed_author_and_committer_date, launch_command,
                      rewrite_definition_file)


class TestForkPoint(BaseTest):

    def test_fork_point_get(self) -> None:
        with fixed_author_and_committer_date():
            (
                self.repo_sandbox.new_branch("master")
                    .commit(message="master commit.")
                    .new_branch("develop")
                    .commit(message="develop commit.")
                    .new_branch("feature")
                    .commit('feature commit.')
            )

        body: str = \
            """
            master
            develop
                feature
            """
        rewrite_definition_file(body)

        # Test `git machete fork-point` without providing the branch name
        # hash 67007ed30def3b9b658380b895a9f62b525286e0 corresponds to the commit on develop branch
        assert_success(["fork-point"], "03e727bb987b21acce75e404f57e9d33ca876c20\n")
        assert_success(["fork-point", "--inferred"], "03e727bb987b21acce75e404f57e9d33ca876c20\n")

        # hash 515319fa0ab47f372f6159bcc8ac27b43ee8a0ed corresponds to the commit on master branch
        assert_success(["fork-point", 'develop'], "58a3121d3ef89189eb51176c7ec5344f4aab2f84\n")

        assert_success(["fork-point", 'refs/heads/develop'], "58a3121d3ef89189eb51176c7ec5344f4aab2f84\n")

    def test_fork_point_override_for_invalid_branch(self) -> None:
        (
            self.repo_sandbox
            .new_branch("master")
            .commit()
        )

        assert_failure(
            ["fork-point", "--override-to=@", "no-such-branch"],
            "no-such-branch is not a local branch"
        )

    def test_fork_point_override_to_non_ancestor_commit(self) -> None:
        with fixed_author_and_committer_date():
            (
                self.repo_sandbox
                .new_branch("master")
                .commit()
                .new_branch("develop")
                .commit()
                .check_out("master")
                .commit()
            )

        assert_failure(
            ["fork-point", "develop", "--override-to=master"],
            "Cannot override fork point: master (commit 4b1e298) is not an ancestor of develop"
        )

    def test_fork_point_override_to_commit(self) -> None:
        (
            self.repo_sandbox.new_branch("master")
                .commit("master first commit")
        )
        master_branch_first_commit_hash = self.repo_sandbox.get_current_commit_hash()
        self.repo_sandbox.commit("master second commit")
        develop_branch_fork_point = self.repo_sandbox.get_current_commit_hash()
        self.repo_sandbox.new_branch("develop").commit("develop commit")
        body: str = \
            """
            master
            develop
            """
        rewrite_definition_file(body)

        # invalid fork point with length not equal to 40
        self.repo_sandbox.set_git_config_key('machete.overrideForkPoint.develop.to', 39 * 'a')
        assert launch_command('fork-point').strip() == develop_branch_fork_point

        # invalid, non-hexadecimal alphanumeric characters present in the fork point
        self.repo_sandbox.set_git_config_key('machete.overrideForkPoint.develop.to', 20 * 'g1')
        assert launch_command('fork-point').strip() == develop_branch_fork_point

        # invalid, non-hexadecimal special characters present in the fork point
        self.repo_sandbox.set_git_config_key('machete.overrideForkPoint.develop.to', 40 * '#')
        assert launch_command('fork-point').strip() == develop_branch_fork_point

        # invalid fork-point override revision
        assert_failure(['fork-point', '--override-to=no-such-commit'], "Cannot find revision no-such-commit")

        # valid commit hash but not present in the repository
        self.repo_sandbox.set_git_config_key('machete.overrideForkPoint.develop.to', 40 * 'a')
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
        with fixed_author_and_committer_date():
            (
                self.repo_sandbox
                .new_branch("master")
                .commit("master  commit")
                .new_branch("in-between")
                .commit("in-between commit")
                .new_branch("develop")
                .commit("develop commit")
            )

        body: str = \
            """
            master
                develop
            """
        rewrite_definition_file(body)

        assert launch_command("fork-point").strip() == "a71ffac2c1d41b8d1592a25f0056e4dfca829608"
        assert launch_command("fork-point", "--inferred").strip() == "a71ffac2c1d41b8d1592a25f0056e4dfca829608"
        assert_success(
            ["status", "--list-commits-with-hashes"],
            """
              master (untracked)
              |
              | a71ffac  in-between commit -> fork point ??? this commit seems to be a part of the unique history of in-between
              | 4aed40c  develop commit
              ?-develop * (untracked)

            Warn: yellow edge indicates that fork point for develop is probably incorrectly inferred,
            or that some extra branch should be between master and develop.

            Consider using git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent develop,
            or reattaching develop under a different parent branch.
            """
        )

        launch_command("fork-point", "--override-to-parent")
        assert launch_command("fork-point").strip() == "7e6757a9e7888e8cad7e112ae4dc305966335594"
        assert launch_command("fork-point", "--inferred").strip() == "a71ffac2c1d41b8d1592a25f0056e4dfca829608"
        assert_success(
            ["status", "-L"],
            """
              master (untracked)
              |
              | a71ffac  in-between commit
              | 4aed40c  develop commit
              o-develop * (untracked)
            """
        )

        launch_command("fork-point", "--override-to-inferred")
        assert launch_command("fork-point").strip() == "a71ffac2c1d41b8d1592a25f0056e4dfca829608"
        assert launch_command("fork-point", "--inferred").strip() == "a71ffac2c1d41b8d1592a25f0056e4dfca829608"
        assert_success(
            ["status", "-L"],
            """
              master (untracked)
              |
              | 4aed40c  develop commit
              o-develop * (untracked)
            """
        )

    def test_fork_point_overridden_to_non_descendant_of_parent_while_branch_descendant_of_parent(self) -> None:
        with fixed_author_and_committer_date():
            (
                self.repo_sandbox
                .new_branch("branch-0")
                .commit()
                .new_branch("branch-1")
                .commit()
                .new_branch("branch-2")
                .commit()
            )

        body: str = \
            """
            branch-1
                branch-2
            """
        rewrite_definition_file(body)
        launch_command('fork-point', '--override-to=branch-0')

        assert launch_command("fork-point").strip() == self.repo_sandbox.get_commit_hash("branch-1")

    def test_fork_point_while_parent_unrelated_to_child(self) -> None:
        (
            self.repo_sandbox
            .new_branch("branch-1")
            .commit()
            .new_orphan_branch("branch-2")
            .commit()
        )

        body: str = \
            """
            branch-1
                branch-2
            """
        rewrite_definition_file(body)

        assert_failure(
            ["fork-point"],
            "Fork point not found for branch branch-2; use git machete fork-point branch-2 --override-to..."
        )

    def test_fork_point_when_no_other_branches(self) -> None:
        (
            self.repo_sandbox
            .new_branch("branch-1")
            .commit()
        )

        assert_failure(
            ["fork-point"],
            "Fork point not found for branch branch-1; use git machete fork-point branch-1 --override-to..."
        )
