
from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, launch_command,
                      rewrite_definition_file)


class TestShow(BaseTest):

    def setup_standard_tree(self) -> None:
        (
            self.repo_sandbox.new_branch("root")
            .commit("root")
            .new_branch("develop")
            .commit("develop commit")
            .new_branch("allow-ownership-link")
            .commit("Allow ownership links")
            .push()
            .new_branch("build-chain")
            .commit("Build arbitrarily long chains")
            .check_out("allow-ownership-link")
            .commit("1st round of fixes")
            .check_out("develop")
            .commit("Other develop commit")
            .push()
            .new_branch("call-ws")
            .commit("Call web service")
            .commit("1st round of fixes")
            .push()
            .new_branch("drop-constraint")
            .commit("Drop unneeded SQL constraints")
            .check_out("call-ws")
            .commit("2nd round of fixes")
            .check_out("root")
            .new_branch("master")
            .commit("Master commit")
            .push()
            .new_branch("hotfix/add-trigger")
            .commit("HOTFIX Add the trigger")
            .push()
            .commit_amend("HOTFIX Add the trigger (amended)")
            .new_branch("ignore-trailing")
            .commit("Ignore trailing data")
            .sleep(1)
            .commit_amend("Ignore trailing data (amended)")
            .push()
            .reset_to("ignore-trailing@{1}")  # noqa: FS003
            .delete_branch("root")
        )

        body: str = \
            """
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
            master
                hotfix/add-trigger
                    ignore-trailing
            """
        rewrite_definition_file(body)

        assert_success(
            ["status"],
            """
            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws (ahead of origin)
              |
              x-drop-constraint (untracked)

            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing * (diverged from & older than origin)
            """
        )

    def test_show(self) -> None:
        self.setup_standard_tree()

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
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1-branch")
            .commit()
        )
        body: str = \
            """
            level-0-branch
                level-1-branch
            """
        rewrite_definition_file(body)

        assert 'level-0-branch' == launch_command("show", "up").strip(), \
            ("Verify that 'git machete show up' displays name of a parent/upstream "
             "branch one above current one.")
        assert 'level-0-branch' == launch_command("show", "u").strip(), \
            ("Verify that 'git machete show u' displays name of a parent/upstream "
             "branch one above current one.")

    def test_show_down(self) -> None:
        """Verify behaviour of a 'git machete show down' command.

        Verify that 'git machete show down' displays name of a
        child/downstream branch one below current one.

        """
        (
            self.repo_sandbox
            .new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .new_branch("level-2-branch")
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .check_out("level-0-branch")
        )
        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2-branch
                level-1b-branch
            """
        rewrite_definition_file(body)

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
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            .new_branch("level-2b-branch")
            .commit()
            .new_branch("level-3b-branch")
            .commit()
            # a added so root will be placed in the config file after the level-0-branch
            .new_orphan_branch("a-additional-root")
            .commit()
            .new_branch("branch-from-a-additional-root")
            .commit()
            .check_out("level-3b-branch")
        )
        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
                    level-2b-branch
                        level-3b-branch
            a-additional-root
                branch-from-a-additional-root
            """
        rewrite_definition_file(body)

        assert 'level-1a-branch' == launch_command("show", "first").strip(), \
            ("Verify that 'git machete show first' displays name of the first downstream "
             "branch of a root branch of the current branch in the config file if root "
             "branch has any downstream branches.")
        assert 'level-1a-branch' == launch_command("show", "f").strip(), \
            ("Verify that 'git machete show f' displays name of the first downstream "
             "branch of a root branch of the current branch in the config file if root "
             "branch has any downstream branches.")

    def test_show_last(self) -> None:
        """Verify behaviour of a 'git machete show last' command.

        Verify that 'git machete show last' displays name of the last downstream
        branch of a root branch of the current branch in the config file if root
        branch has any downstream branches.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            # x added so root will be placed in the config file after the level-0-branch
            .new_orphan_branch("x-additional-root")
            .commit()
            .new_branch("branch-from-x-additional-root")
            .commit()
            .check_out("level-1a-branch")
        )
        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            x-additional-root
                branch-from-x-additional-root
            """
        rewrite_definition_file(body)

        assert 'level-1b-branch' == launch_command("show", "last").strip(), \
            ("Verify that 'git machete show last' displays name of the last downstream "
             "branch of a root branch of the current branch in the config file if root "
             "branch has any downstream branches.")
        assert 'level-1b-branch' == launch_command("show", "l").strip(), \
            ("Verify that 'git machete show l' displays name of the last downstream "
             "branch of a root branch of the current branch in the config file if root "
             "branch has any downstream branches.")

    def test_show_next(self) -> None:
        """Verify behaviour of a 'git machete show next' command.

        Verify that 'git machete show next' displays name of
        a branch right after the current one in the config file
        when successor branch exists within the root tree.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            .check_out("level-2a-branch")
        )
        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            """
        rewrite_definition_file(body)

        assert launch_command("show", "next").strip() == 'level-1b-branch'
        assert launch_command("show", "n").strip() == 'level-1b-branch'
        assert_failure(["show", "n", "level-1b-branch"], "Branch level-1b-branch has no successor")

    def test_show_prev(self) -> None:
        """Verify behaviour of a 'git machete show prev' command.

        Verify that 'git machete show prev' displays name of
        a branch right before the current one in the config file
        when predecessor branch exists within the root tree.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
        )
        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            """
        rewrite_definition_file(body)

        assert launch_command("show", "prev").strip() == 'level-2a-branch'
        assert launch_command("show", "p").strip() == 'level-2a-branch'
        assert_failure(["show", "p", "level-0-branch"], "Branch level-0-branch has no predecessor")

    def test_show_root(self) -> None:
        """Verify behaviour of a 'git machete show root' command.

        Verify that 'git machete show root' displays name of the root of
        the current branch.
        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            .new_orphan_branch("additional-root")
            .commit()
            .new_branch("branch-from-additional-root")
            .commit()
            .check_out("level-2a-branch")
        )
        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            additional-root
                branch-from-additional-root
            """
        rewrite_definition_file(body)

        assert 'level-0-branch' == launch_command("show", "root").strip(), \
            ("Verify that 'git machete show root' displays name of the root of "
             "the current branch.")
        assert 'level-0-branch' == launch_command("show", "r").strip(), \
            ("Verify that 'git machete show r' displays name of the root of "
             "the current branch.")
