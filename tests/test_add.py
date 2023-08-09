from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, mock_input_returning,
                      mock_input_returning_y, rewrite_branch_layout_file)


class TestAdd(BaseTest):

    def test_add(self, mocker: MockerFixture) -> None:
        (
            self.repo_sandbox.new_branch("master")
                .commit("master commit.")
                .new_branch("develop")
                .commit("develop commit.")
                .new_branch("feature")
                .commit("feature commit.")
                .check_out("develop")
                .commit("New commit on develop")
        )
        body: str = \
            """
            master
                develop
                    feature
            """
        rewrite_branch_layout_file(body)

        self.repo_sandbox.new_branch("bugfix/feature_fail")

        # Test `git machete add` without providing the branch name
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        assert_success(
            ['add'],
            'Add bugfix/feature_fail onto the inferred upstream (parent) branch develop? (y, N)\n'
        )
        assert_success(
            ['add', '-y'],
            'Adding bugfix/feature_fail onto the inferred upstream (parent) branch develop\n'
            'Added branch bugfix/feature_fail onto develop\n'
        )

        self.repo_sandbox.check_out('develop')
        self.repo_sandbox.new_branch("bugfix/some_feature")
        assert_success(
            ['add', '-y', 'bugfix/some_feature'],
            'Adding bugfix/some_feature onto the inferred upstream (parent) branch develop\n'
            'Added branch bugfix/some_feature onto develop\n'
        )

        self.repo_sandbox.check_out('develop')
        self.repo_sandbox.new_branch("bugfix/another_feature")
        assert_success(
            ['add', '-y', 'refs/heads/bugfix/another_feature'],
            'Adding bugfix/another_feature onto the inferred upstream (parent) branch develop\n'
            'Added branch bugfix/another_feature onto develop\n'
        )

        # test with --onto option
        self.repo_sandbox.new_branch("chore/remove_indentation")

        assert_success(
            ['add', '--onto=feature'],
            'Added branch chore/remove_indentation onto feature\n'
        )

    def test_add_check_out_remote_branch(self, mocker: MockerFixture) -> None:
        """
        Verify the behaviour of a 'git machete add' command in the special case when a remote branch is checked out locally.
        """

        (
            self.repo_sandbox.new_branch("master")
            .commit("master commit.")
            .new_branch("feature/foo")
            .push()
            .check_out("master")
            .delete_branch("feature/foo")
        )

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        assert_success(
            ['add', 'foo'],
            'A local branch foo does not exist. Create out of the current HEAD? (y, N)\n'
        )

        assert_success(
            ['add', '-y', 'foo'],
            'A local branch foo does not exist. Creating out of the current HEAD\n'
            'Added branch foo as a new root\n'
        )

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        assert_success(
            ['add', '--as-root', 'feature/foo'],
            'A local branch feature/foo does not exist, but a remote branch origin/feature/foo exists.\n'
            'Check out feature/foo locally? (y, N)\n'
        )

        assert_success(
            ['add', '-y', '--as-root', 'feature/foo'],
            'A local branch feature/foo does not exist, but a remote branch origin/feature/foo exists.\n'
            'Checking out feature/foo locally...\n'
            'Added branch feature/foo as a new root\n'
        )

    def test_add_new_branch_onto_managed_current_branch(self, mocker: MockerFixture) -> None:
        (
            self.repo_sandbox.new_branch("master")
            .commit()
        )

        rewrite_branch_layout_file("master")

        self.patch_symbol(mocker, "builtins.input", mock_input_returning_y)
        assert_success(
            ['add', 'foo'],
            "A local branch foo does not exist. Create out of the current HEAD? (y, N)\n"
            "Added branch foo onto master\n"
        )

    def test_add_new_branch_when_cannot_infer_parent(self, mocker: MockerFixture) -> None:
        (
            self.repo_sandbox.new_branch("master")
            .commit()
            .new_branch("develop")
            .commit()
            .check_out("master")
        )

        rewrite_branch_layout_file("develop")

        self.patch_symbol(mocker, "builtins.input", mock_input_returning_y)
        assert_failure(
            ['add', 'foo'],
            """
            Could not automatically infer upstream (parent) branch for foo.
            You can either:
            1) specify the desired upstream branch with --onto or
            2) pass --as-root to attach foo as a new root or
            3) edit the branch layout file manually with git machete edit"""
        )

    def test_add_already_managed_branch(self) -> None:
        (
            self.repo_sandbox.new_branch("master")
            .commit("master commit.")
            .new_branch("develop")
            .commit("develop commit.")
        )

        rewrite_branch_layout_file("master\n  develop")

        assert_failure(['add', 'develop'], 'Branch develop already exists in the tree of branch dependencies')

    def test_add_onto_non_existent_branch(self) -> None:
        (
            self.repo_sandbox.new_branch("master")
            .commit("master commit.")
            .new_branch("develop")
            .commit("develop commit.")
        )

        rewrite_branch_layout_file("master")

        assert_failure(
            ['add', 'develop', '--onto', 'foo'],
            "Branch foo not found in the tree of branch dependencies.\n"
            "Use git machete add foo or git machete edit."
        )

    def test_add_as_root_with_onto(self) -> None:
        assert_failure(
            ['add', '--onto', 'foo', '--as-root'],
            "Option -R/--as-root cannot be specified together with -o/--onto."
        )
