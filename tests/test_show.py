import os

from git_machete.utils import ExitCode

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, execute, launch_command,
                      launch_command_capturing_output_and_exception,
                      remove_directory, rewrite_branch_layout_file)
from .mockers_git_repository import (check_out, commit, create_repo,
                                     create_repo_with_remote, new_branch,
                                     new_orphan_branch, pull, push)


class TestShow(BaseTest):

    def test_show(self) -> None:
        create_repo()
        new_branch("develop")
        commit()
        new_branch("call-ws")
        commit()
        new_branch("hotfix/add-trigger")
        commit()
        new_branch("ignore-trailing")
        commit()

        body: str = \
            """
            develop
                call-ws
            hotfix/add-trigger
                ignore-trailing
            """
        rewrite_branch_layout_file(body)

        assert launch_command("show", "up").strip() == "hotfix/add-trigger"
        assert launch_command("show", "up", "call-ws").strip() == "develop"
        assert launch_command("show", "up", "refs/heads/call-ws").strip() == "develop"
        assert launch_command("show", "current").strip() == "ignore-trailing"

    def test_show_current_with_branch(self) -> None:
        assert_failure(["show", "current", "master"], "show current with a <branch> argument does not make sense")

    def test_show_up(self) -> None:
        """Verify behaviour of a 'git machete show up' command.

        Verify that 'git machete show up' displays name of a parent/upstream
        branch one above current one in the config file from within current
        root tree.
        """
        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1-branch")
        commit()

        body: str = \
            """
            level-0-branch
                level-1-branch
            """
        rewrite_branch_layout_file(body)

        assert 'level-0-branch' == launch_command("show", "up").strip(), \
            ("Verify that 'git machete show up' displays name of a parent/upstream "
             "branch one above current one.")
        assert 'level-0-branch' == launch_command("show", "u").strip(), \
            ("Verify that 'git machete show u' displays name of a parent/upstream "
             "branch one above current one.")

    def test_show_up_inference_using_reflog_of_remote_branch(self) -> None:
        (local_path, remote_path) = create_repo_with_remote()
        new_branch("master")
        commit()
        push()

        new_branch("develop")
        commit()
        push()

        os.chdir(remote_path)
        execute("git update-ref refs/heads/master develop")
        os.chdir(local_path)

        check_out("master")
        pull()
        check_out("develop")

        assert_success(
            ["show", "up"],
            "Warn: branch develop not found in the tree of branch dependencies; the upstream has been inferred to master\n"
            "master\n"
        )

        remove_directory(".git/logs/refs/heads/")

        assert_success(
            ["show", "up"],
            "Warn: branch develop not found in the tree of branch dependencies; the upstream has been inferred to master\n"
            "master\n"
        )

    def test_show_down(self) -> None:
        """Verify behaviour of a 'git machete show down' command.

        Verify that 'git machete show down' displays name of a
        child/downstream branch one below current one.
        """
        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        new_branch("level-2-branch")
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        check_out("level-0-branch")

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2-branch
                level-1b-branch
            """
        rewrite_branch_layout_file(body)

        assert launch_command("show", "down").strip() == "level-1a-branch\nlevel-1b-branch"
        assert launch_command("show", "d").strip() == "level-1a-branch\nlevel-1b-branch"
        assert launch_command("show", "d", "level-1a-branch").strip() == "level-2-branch"
        assert_failure(["show", "d", "level-1b-branch"], "Branch level-1b-branch has no downstream branch")

    def test_show_first(self) -> None:
        """Verify behaviour of a 'git machete show first' command.

        Verify that 'git machete show first' displays name of the first downstream
        branch of a root branch of the current branch in the config file if root
        branch has any downstream branches.
        """
        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        commit()
        new_branch("level-2b-branch")
        commit()
        new_branch("level-3b-branch")
        commit()
        # a added so root will be placed in the config file after the level-0-branch
        new_orphan_branch("a-additional-root")
        commit()
        new_branch("branch-from-a-additional-root")
        commit()
        check_out("level-3b-branch")

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
                    level-2b-branch
            a-additional-root
                branch-from-a-additional-root
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ["show", "first"],
            "Warn: level-3b-branch is not a managed branch, assuming "
            "level-0-branch (the first root) instead as root\n"
            "level-1a-branch\n",
        )
        assert_success(
            ["show", "f"],
            "Warn: level-3b-branch is not a managed branch, assuming "
            "level-0-branch (the first root) instead as root\n"
            "level-1a-branch\n",
        )

    def test_show_last(self) -> None:
        """Verify behaviour of a 'git machete show last' command.

        Verify that 'git machete show last' displays name of the last downstream
        branch of a root branch of the current branch in the config file if root
        branch has any downstream branches.

        """
        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        commit()
        new_branch("level-2b-branch")
        commit()
        # x added so root will be placed in the config file after the level-0-branch
        new_orphan_branch("x-additional-root")
        commit()
        new_branch("branch-from-x-additional-root")
        commit()
        check_out("level-2b-branch")

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            x-additional-root
                branch-from-x-additional-root
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ["show", "last"],
            "Warn: level-2b-branch is not a managed branch, assuming "
            "x-additional-root (the last root) instead as root\n"
            "branch-from-x-additional-root\n",
        )
        assert_success(
            ["show", "l"],
            "Warn: level-2b-branch is not a managed branch, assuming "
            "x-additional-root (the last root) instead as root\n"
            "branch-from-x-additional-root\n",
        )

    def test_show_next(self) -> None:
        """Verify behaviour of a 'git machete show next' command.

        Verify that 'git machete show next' displays name of
        a branch right after the current one in the config file
        when successor branch exists within the root tree.

        """
        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        commit()
        check_out("level-2a-branch")

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            """
        rewrite_branch_layout_file(body)

        assert launch_command("show", "next").strip() == 'level-1b-branch'
        assert launch_command("show", "n").strip() == 'level-1b-branch'
        assert_failure(["show", "n", "level-1b-branch"], "Branch level-1b-branch has no successor")

    def test_show_prev(self) -> None:
        """Verify behaviour of a 'git machete show prev' command.

        Verify that 'git machete show prev' displays name of
        a branch right before the current one in the config file
        when predecessor branch exists within the root tree.

        """
        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        commit()

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            """
        rewrite_branch_layout_file(body)

        assert launch_command("show", "prev").strip() == 'level-2a-branch'
        assert launch_command("show", "p").strip() == 'level-2a-branch'
        assert_failure(["show", "p", "level-0-branch"], "Branch level-0-branch has no predecessor")

    def test_show_root(self) -> None:
        """Verify behaviour of a 'git machete show root' command.

        Verify that 'git machete show root' displays name of the root of
        the current branch.
        """
        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        commit()
        new_orphan_branch("additional-root")
        commit()
        new_branch("branch-from-additional-root")
        commit()
        check_out("level-2a-branch")

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            additional-root
                branch-from-additional-root
            """
        rewrite_branch_layout_file(body)

        assert 'level-0-branch' == launch_command("show", "root").strip(), \
            ("Verify that 'git machete show root' displays name of the root of "
             "the current branch.")
        assert 'level-0-branch' == launch_command("show", "r").strip(), \
            ("Verify that 'git machete show r' displays name of the root of "
             "the current branch.")

        new_branch("not-in-machete-layout")
        commit()
        check_out("not-in-machete-layout")
        assert_success(
            ["show", "root"],
            "Warn: not-in-machete-layout is not a managed branch, assuming "
            "level-0-branch (the first root) instead as root\n"
            "level-0-branch\n",
        )
        assert_success(
            ["show", "r"],
            "Warn: not-in-machete-layout is not a managed branch, assuming "
            "level-0-branch (the first root) instead as root\n"
            "level-0-branch\n",
        )

    def test_show_missing_direction(self) -> None:
        output, e = launch_command_capturing_output_and_exception("show")
        assert output == \
            "the following arguments are required: show direction\n" \
            "Possible values for show direction are: c, current, d, down, f, first, l, last, n, next, p, prev, r, root, u, up\n"
        assert type(e) is SystemExit
        assert e.code == ExitCode.ARGUMENT_ERROR
