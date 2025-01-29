from pytest_mock import MockerFixture

from .base_test import BaseTest, GitRepositorySandbox
from .mockers import (assert_failure, assert_success, mock_input_returning,
                      mock_input_returning_y, read_branch_layout_file,
                      rewrite_branch_layout_file)


class TestAdd(BaseTest):

    def test_add(self, mocker: MockerFixture) -> None:
        repo_sandbox = GitRepositorySandbox()
        (
            repo_sandbox
            .remove_remote("origin")
            .new_branch("master")
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

        repo_sandbox.new_branch("bugfix/feature_fail")

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

        repo_sandbox.check_out('develop')
        repo_sandbox.new_branch("bugfix/some_feature")
        assert_success(
            ['add', '-y', 'bugfix/some_feature'],
            'Adding bugfix/some_feature onto the inferred upstream (parent) branch develop\n'
            'Added branch bugfix/some_feature onto develop\n'
        )

        repo_sandbox.check_out('develop')
        repo_sandbox.new_branch("bugfix/another_feature")
        assert_success(
            ['add', '--as-first-child', '-y', 'refs/heads/bugfix/another_feature'],
            'Adding bugfix/another_feature onto the inferred upstream (parent) branch develop\n'
            'Added branch bugfix/another_feature onto develop\n'
        )

        # test with --onto option
        repo_sandbox.new_branch("chore/remove_indentation")

        assert_success(
            ['add', '--onto=feature'],
            'Added branch chore/remove_indentation onto feature\n'
        )

        assert_success(["status"], """
            master
            |
            o-develop
              |
              o-bugfix/another_feature
              |
              x-feature
              | |
              | x-chore/remove_indentation *
              |
              o-bugfix/feature_fail
              |
              o-bugfix/some_feature
        """)

    def test_add_check_out_remote_branch(self, mocker: MockerFixture) -> None:
        """
        Verify the behaviour of a 'git machete add' command in the special case when a remote branch is checked out locally.
        """

        (
            GitRepositorySandbox()
            .new_branch("master")
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
            'Added branch master as a new root\n'
            'Added branch foo onto master\n'
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
            GitRepositorySandbox()
            .new_branch("master")
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
            GitRepositorySandbox()
            .new_branch("master")
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
            GitRepositorySandbox()
            .new_branch("master")
            .commit("master commit.")
            .new_branch("develop")
            .commit("develop commit.")
        )

        rewrite_branch_layout_file("master\n  develop")

        assert_failure(['add', 'develop'], 'Branch develop already exists in the tree of branch dependencies')

    def test_add_onto_non_existent_branch(self) -> None:
        (
            GitRepositorySandbox()
            .new_branch("master")
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

    def test_add_new_branch_onto_master_for_fresh_start_with_yes(self) -> None:
        GitRepositorySandbox().new_branch("master").commit("master commit.")
        assert_success(
            ['add', '--yes', 'foo'],
            """
            A local branch foo does not exist. Creating out of the current HEAD
            Added branch master as a new root
            Added branch foo onto master
            """)
        assert read_branch_layout_file() == "master\n  foo\n"

    def test_add_new_branch_with_onto(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        (
            repo_sandbox
            .new_branch("master").commit()
            .new_branch("develop").commit()
        )

        body: str = \
            """
            master
              develop
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['add', '--onto=master', '--yes', 'foo'],
            """
            A local branch foo does not exist. Creating out of master
            Added branch foo onto master
            """)
        assert read_branch_layout_file() == "master\n  develop\n  foo\n"
        assert repo_sandbox.get_commit_hash("master") == repo_sandbox.get_commit_hash("foo")

    def test_add_new_branch_when_detached_head_for_fresh_start(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        GitRepositorySandbox().new_branch("master").commit("master commit.")\
            .check_out(repo_sandbox.get_current_commit_hash())
        assert_success(
            ['add', '--yes', 'foo'],
            """
            A local branch foo does not exist. Creating out of the current HEAD
            Added branch foo as a new root
            """)
        assert read_branch_layout_file() == "foo\n"

    def test_add_new_branch_onto_master_for_fresh_start_without_yes(self, mocker: MockerFixture) -> None:
        GitRepositorySandbox().new_branch("master").commit("master commit.")

        self.patch_symbol(mocker, "builtins.input", mock_input_returning_y)
        assert_success(
            ['add', 'foo'],
            """
            A local branch foo does not exist. Create out of the current HEAD? (y, N)
            Added branch master as a new root
            Added branch foo onto master
            """)
        assert read_branch_layout_file() == "master\n  foo\n"

    def test_add_as_root_with_onto(self) -> None:
        assert_failure(
            ['add', '--onto', 'foo', '--as-root'],
            "Option -R/--as-root cannot be specified together with -o/--onto."
        )

    def test_add_as_root_with_as_first_child(self) -> None:
        assert_failure(
            ['add', '--as-first-child', '--as-root'],
            "Option -R/--as-root cannot be specified together with -f/--as-first-child."
        )
