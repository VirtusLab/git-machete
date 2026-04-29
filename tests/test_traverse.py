# flake8: noqa: E501
import os
import textwrap

import pytest
from pytest_mock import MockerFixture

from git_machete.utils import (FullTerminalAnsiOutputCodes,
                               UnderlyingGitException)

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success,
                      fixed_author_and_committer_date_in_past, launch_command,
                      mock_input_returning, mock_input_returning_y,
                      overridden_environment, rewrite_branch_layout_file,
                      sleep, write_to_file)
from .mockers_git_repository import (add_file_and_commit, add_remote,
                                     amend_commit, check_out, commit,
                                     create_repo, create_repo_with_remote,
                                     delete_branch, get_current_branch,
                                     get_git_version, merge, new_branch, push,
                                     remove_remote, reset_to,
                                     set_git_config_key)


class TestTraverse(BaseTest):

    def setup_standard_tree(self) -> None:
        create_repo_with_remote()
        new_branch("root")
        commit("root")
        new_branch("develop")
        commit("develop commit")
        new_branch("allow-ownership-link")
        commit("Allow ownership links")
        push()
        new_branch("build-chain")
        commit("Build arbitrarily long chains")
        check_out("allow-ownership-link")
        commit("1st round of fixes")
        check_out("develop")
        commit("Other develop commit")
        push()
        new_branch("call-ws")
        commit("Call web service")
        commit("1st round of fixes")
        push()
        new_branch("drop-constraint")
        commit("Drop unneeded SQL constraints")
        check_out("call-ws")
        commit("2nd round of fixes")
        check_out("root")
        new_branch("master")
        commit("Master commit")
        push()
        new_branch("hotfix/add-trigger")
        commit("HOTFIX Add the trigger")
        push()
        amend_commit("HOTFIX Add the trigger (amended)")
        new_branch("ignore-trailing")
        commit("Ignore trailing data")
        sleep(1)
        amend_commit("Ignore trailing data (amended)")
        push()
        reset_to("ignore-trailing@{1}")  # noqa: FS003
        delete_branch("root")

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
        rewrite_branch_layout_file(body)

    def test_traverse_slide_out(self, mocker: MockerFixture) -> None:
        E = FullTerminalAnsiOutputCodes
        self.patch_symbol(mocker, "git_machete.utils.is_stdout_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_stderr_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_terminal_fully_fledged", lambda: True)

        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        new_branch("feature")
        commit("feature commit")
        check_out("master")
        merge("develop")
        check_out("develop")

        body: str = \
            """
            master
                develop  PR #123
                    feature
            """
        rewrite_branch_layout_file(body)

        pc = f"({E.GREEN}y{E.ENDC}, {E.RED}N{E.ENDC}, {E.RED}q{E.ENDC}, {E.GREEN}y{E.ENDC}{E.RED}q{E.ENDC})"
        slide_msg = f"Branch {E.BOLD}develop{E.ENDC_BOLD_DIM} is merged into {E.BOLD}master{E.ENDC_BOLD_DIM}. Slide {E.BOLD}develop{E.ENDC_BOLD_DIM} out of the tree of branch dependencies? {pc}"

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse"],
            textwrap.dedent(f"""\
            {slide_msg}

              {E.BOLD}master{E.ENDC_BOLD_DIM}
              {E.DIM}│{E.ENDC_BOLD_DIM}
              {E.DIM}└─{E.ENDC_BOLD_DIM}{E.BOLD}{E.UNDERLINE}develop{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}  {E.DIM}PR #123{E.ENDC_BOLD_DIM}
                {E.GREEN}│{E.ENDC}
                {E.GREEN}└─{E.ENDC}{E.BOLD}feature{E.ENDC_BOLD_DIM}

            No successor of {E.BOLD}develop{E.ENDC_BOLD_DIM} needs to be slid out or synced with upstream branch or remote; nothing left to update
            """)
        )
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(["traverse"], f"{slide_msg}\n")
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(["traverse"], f"{slide_msg}\n")
        assert_success(
            ["status", "-l"],
            textwrap.dedent(f"""\
              {E.BOLD}master{E.ENDC_BOLD_DIM}
              {E.GREEN}│{E.ENDC}
              {E.GREEN}│{E.ENDC} {E.DIM}feature commit{E.ENDC_BOLD_DIM}
              {E.GREEN}└─{E.ENDC}{E.BOLD}feature{E.ENDC_BOLD_DIM}
            """)
        )

        check_out("master")
        merge("feature")
        check_out("feature")

        slide_msg2 = f"Branch {E.BOLD}feature{E.ENDC_BOLD_DIM} is merged into {E.BOLD}master{E.ENDC_BOLD_DIM}. Slide {E.BOLD}feature{E.ENDC_BOLD_DIM} out of the tree of branch dependencies? {pc}"
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("Y "))
        assert_success(
            ["traverse"],
            textwrap.dedent(f"""\
            {slide_msg2}

              {E.BOLD}master{E.ENDC_BOLD_DIM}

            No successor of {E.BOLD}feature{E.ENDC_BOLD_DIM} needs to be slid out or synced with upstream branch or remote; nothing left to update
            """)
        )

    def test_traverse_no_remotes(self) -> None:
        self.setup_standard_tree()
        remove_remote()

        launch_command("traverse", "-Wy")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws
              |
              | Drop unneeded SQL constraints
              o-drop-constraint

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger
              |
              | Ignore trailing data
              o-ignore-trailing *
            """
        )

    def test_traverse_no_push(self) -> None:
        self.setup_standard_tree()

        launch_command("traverse", "-Wy", "--no-push")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link (diverged from origin)
            | |
            | | Build arbitrarily long chains
            | o-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws (ahead of origin)
              |
              | Drop unneeded SQL constraints
              o-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger (diverged from origin)
              |
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

    def test_traverse_no_push_override(self) -> None:
        self.setup_standard_tree()
        check_out("hotfix/add-trigger")
        launch_command("t", "-Wy", "--no-push", "--push", "--start-from=here")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            x-allow-ownership-link (ahead of origin)
            | |
            | | Build arbitrarily long chains
            | x-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws (ahead of origin)
              |
              | Drop unneeded SQL constraints
              x-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger *
              |
              | Ignore trailing data (amended)
              o-ignore-trailing
            """,
        )
        check_out("ignore-trailing")
        set_git_config_key("machete.traverse.push", "false")
        launch_command("t", "-Wy")
        assert_success(
            ["status"],
            """
            develop
            |
            o-allow-ownership-link (diverged from origin)
            | |
            | o-build-chain (untracked)
            |
            o-call-ws (ahead of origin)
              |
              o-drop-constraint (untracked)

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing *
            """,
        )

        launch_command("t", "-Wy", "--push-untracked")
        assert_success(
            ["status"],
            """
            develop
            |
            o-allow-ownership-link (diverged from origin)
            | |
            | o-build-chain
            |
            o-call-ws (ahead of origin)
              |
              o-drop-constraint

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing *
            """,
        )

        set_git_config_key("machete.traverse.push", "true")
        launch_command("t", "-Wy", "--no-push-untracked")
        assert_success(
            ["status"],
            """
            develop
            |
            o-allow-ownership-link
            | |
            | o-build-chain
            |
            o-call-ws
              |
              o-drop-constraint

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing *
            """,
        )

    def test_traverse_ahead_of_remote_responses(self, mocker: MockerFixture) -> None:
        E = FullTerminalAnsiOutputCodes
        self.patch_symbol(mocker, "git_machete.utils.is_stdout_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_stderr_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_terminal_fully_fledged", lambda: True)

        create_repo_with_remote()
        new_branch("master")
        commit()
        push()
        commit()

        rewrite_branch_layout_file("master")

        pc = f"({E.GREEN}y{E.ENDC}, {E.RED}N{E.ENDC}, {E.RED}q{E.ENDC}, {E.GREEN}y{E.ENDC}{E.RED}q{E.ENDC})"

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("Q  "))
        assert_success(["traverse"], f"Push {E.BOLD}master{E.ENDC_BOLD_DIM} to {E.BOLD}origin{E.ENDC_BOLD_DIM}? {pc}\n")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning(" n"))
        assert_success(
            ["traverse"],
            textwrap.dedent(f"""\
            Push {E.BOLD}master{E.ENDC_BOLD_DIM} to {E.BOLD}origin{E.ENDC_BOLD_DIM}? {pc}

              {E.BOLD}{E.UNDERLINE}master{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}{E.RED} (ahead of {E.BOLD}origin{E.ENDC_BOLD_DIM}){E.ENDC}

            Reached branch {E.BOLD}master{E.ENDC_BOLD_DIM} which has no successor; nothing left to update
            """)
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning(" yQ "))
        assert_success(["traverse"], f"Push {E.BOLD}master{E.ENDC_BOLD_DIM} to {E.BOLD}origin{E.ENDC_BOLD_DIM}? {pc}\n")

    def test_traverse_behind_remote_responses(self, mocker: MockerFixture) -> None:
        E = FullTerminalAnsiOutputCodes
        self.patch_symbol(mocker, "git_machete.utils.is_stdout_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_stderr_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_terminal_fully_fledged", lambda: True)

        create_repo_with_remote()
        new_branch("master")
        commit()
        commit()
        push()
        reset_to("HEAD~")
        rewrite_branch_layout_file("master")

        pc = f"({E.GREEN}y{E.ENDC}, {E.RED}N{E.ENDC}, {E.RED}q{E.ENDC}, {E.GREEN}y{E.ENDC}{E.RED}q{E.ENDC})"
        rb = f"{E.BOLD}origin/master{E.ENDC_BOLD_DIM}"

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(
            ["traverse"],
            textwrap.dedent(f"""\
            Branch {E.BOLD}master{E.ENDC_BOLD_DIM} is behind its remote counterpart {rb}.
            Pull {E.BOLD}master{E.ENDC_BOLD_DIM} (fast-forward only) from {E.BOLD}origin{E.ENDC_BOLD_DIM}? {pc}
            """)
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse"],
            textwrap.dedent(f"""\
            Branch {E.BOLD}master{E.ENDC_BOLD_DIM} is behind its remote counterpart {rb}.
            Pull {E.BOLD}master{E.ENDC_BOLD_DIM} (fast-forward only) from {E.BOLD}origin{E.ENDC_BOLD_DIM}? {pc}

              {E.BOLD}{E.UNDERLINE}master{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}{E.RED} (behind {E.BOLD}origin{E.ENDC_BOLD_DIM}){E.ENDC}

            Reached branch {E.BOLD}master{E.ENDC_BOLD_DIM} which has no successor; nothing left to update
            """)
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(
            ["traverse"],
            textwrap.dedent(f"""\
            Branch {E.BOLD}master{E.ENDC_BOLD_DIM} is behind its remote counterpart {rb}.
            Pull {E.BOLD}master{E.ENDC_BOLD_DIM} (fast-forward only) from {E.BOLD}origin{E.ENDC_BOLD_DIM}? {pc}
            """)
        )

    def test_traverse_diverged_from_and_newer_responses(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()
        new_branch("master")
        commit()
        push()
        amend_commit("Different commit message")

        rewrite_branch_layout_file("master")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has newer commits than) its remote counterpart origin/master.
            Push master with force-with-lease to origin? (y, N, q, yq)
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has newer commits than) its remote counterpart origin/master.
            Push master with force-with-lease to origin? (y, N, q, yq)

              master * (diverged from origin)

            Reached branch master which has no successor; nothing left to update
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has newer commits than) its remote counterpart origin/master.
            Push master with force-with-lease to origin? (y, N, q, yq)
            """
        )

    def test_traverse_diverged_from_and_older_responses(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()
        new_branch("master")
        commit()
        push()

        with fixed_author_and_committer_date_in_past():
            amend_commit()
        rewrite_branch_layout_file("master")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has older commits than) its remote counterpart origin/master.
            Reset branch master to the commit pointed by origin/master? (y, N, q, yq)
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has older commits than) its remote counterpart origin/master.
            Reset branch master to the commit pointed by origin/master? (y, N, q, yq)

              master * (diverged from & older than origin)

            Reached branch master which has no successor; nothing left to update
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has older commits than) its remote counterpart origin/master.
            Reset branch master to the commit pointed by origin/master? (y, N, q, yq)
            """
        )

    def test_traverse_no_push_untracked(self) -> None:
        self.setup_standard_tree()

        launch_command("traverse", "-Wy", "--no-push-untracked")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws
              |
              | Drop unneeded SQL constraints
              o-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger
              |
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

    def test_traverse_push_config_key(self) -> None:
        self.setup_standard_tree()
        set_git_config_key('machete.traverse.push', 'false')
        launch_command("traverse", "-Wy")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link (diverged from origin)
            | |
            | | Build arbitrarily long chains
            | o-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws (ahead of origin)
              |
              | Drop unneeded SQL constraints
              o-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger (diverged from origin)
              |
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

    def test_traverse_no_push_no_checkout(self, mocker: MockerFixture) -> None:
        E = FullTerminalAnsiOutputCodes
        self.patch_symbol(mocker, "git_machete.utils.is_stdout_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_stderr_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_terminal_fully_fledged", lambda: True)

        create_repo_with_remote()
        new_branch("root")
        commit("root")
        new_branch("develop")
        commit("develop commit")
        commit("Other develop commit")
        push()
        new_branch("allow-ownership-link")
        commit("Allow ownership links")
        push()
        check_out("allow-ownership-link")
        commit("1st round of fixes")
        new_branch("build-chain")
        commit("Build arbitrarily long chains")
        check_out("root")
        new_branch("master")
        commit("Master commit")
        push()
        new_branch("hotfix/add-trigger")
        commit("HOTFIX Add the trigger")
        push()
        amend_commit("HOTFIX Add the trigger (amended)")
        delete_branch("root")

        body: str = \
            """
            develop
                allow-ownership-link
                    build-chain
            master
                hotfix/add-trigger
            """
        rewrite_branch_layout_file(body)
        ok = f"{E.GREEN}{E.BOLD}OK{E.ENDC_BOLD_DIM}{E.ENDC}"
        assert_success(
            ["status"],
            textwrap.dedent(f"""\
              {E.BOLD}develop{E.ENDC_BOLD_DIM}
              {E.GREEN}│{E.ENDC}
              {E.GREEN}└─{E.ENDC}{E.BOLD}allow-ownership-link{E.ENDC_BOLD_DIM}{E.RED} (ahead of {E.BOLD}origin{E.ENDC_BOLD_DIM}){E.ENDC}
                {E.GREEN}│{E.ENDC}
                {E.GREEN}└─{E.ENDC}{E.BOLD}build-chain{E.ENDC_BOLD_DIM}{E.ORANGE} (untracked){E.ENDC}

              {E.BOLD}master{E.ENDC_BOLD_DIM}
              {E.GREEN}│{E.ENDC}
              {E.GREEN}└─{E.ENDC}{E.BOLD}{E.UNDERLINE}hotfix/add-trigger{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}{E.RED} (diverged from {E.BOLD}origin{E.ENDC_BOLD_DIM}){E.ENDC}
            """)
        )

        expected_result = textwrap.dedent(f'''\
        Fetching {E.BOLD}origin{E.ENDC_BOLD_DIM}...

        Checking out the first root branch ({E.BOLD}develop{E.ENDC_BOLD_DIM})... {ok}
        Checking out {E.BOLD}hotfix/add-trigger{E.ENDC_BOLD_DIM}... {ok}

          {E.BOLD}develop{E.ENDC_BOLD_DIM}
          {E.GREEN}│{E.ENDC}
          {E.GREEN}└─{E.ENDC}{E.BOLD}allow-ownership-link{E.ENDC_BOLD_DIM}{E.RED} (ahead of {E.BOLD}origin{E.ENDC_BOLD_DIM}){E.ENDC}
            {E.GREEN}│{E.ENDC}
            {E.GREEN}└─{E.ENDC}{E.BOLD}build-chain{E.ENDC_BOLD_DIM}{E.ORANGE} (untracked){E.ENDC}

          {E.BOLD}master{E.ENDC_BOLD_DIM}
          {E.GREEN}│{E.ENDC}
          {E.GREEN}└─{E.ENDC}{E.BOLD}{E.UNDERLINE}hotfix/add-trigger{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}{E.RED} (diverged from {E.BOLD}origin{E.ENDC_BOLD_DIM}){E.ENDC}

        No successor of {E.BOLD}develop{E.ENDC_BOLD_DIM} needs to be slid out or synced with upstream branch or remote; nothing left to update
        Tip: {E.UNDERLINE}traverse{E.ENDC_UNDERLINE} by default starts from the current branch, use flags ({E.UNDERLINE}--start-from={E.ENDC_UNDERLINE}, {E.UNDERLINE}--whole{E.ENDC_UNDERLINE} or {E.UNDERLINE}-w{E.ENDC_UNDERLINE}, {E.UNDERLINE}-W{E.ENDC_UNDERLINE}) to change this behavior.
        Further info under {E.UNDERLINE}git machete traverse --help{E.ENDC_UNDERLINE}.
        Returned to the initial branch {E.BOLD}hotfix/add-trigger{E.ENDC_BOLD_DIM}
        ''')
        assert_success(["traverse", "-Wy", "--no-push"],
                       expected_result)

    def test_traverse_and_squash(self) -> None:
        self.setup_standard_tree()

        check_out("hotfix/add-trigger")
        launch_command("traverse", "--fetch", "--start-from=root", "--return-to=here", "-y")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            x-allow-ownership-link (ahead of origin)
            | |
            | | Build arbitrarily long chains
            | x-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws (ahead of origin)
              |
              | Drop unneeded SQL constraints
              x-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger *
              |
              | Ignore trailing data (amended)
              o-ignore-trailing
            """,
        )
        assert get_current_branch() == "hotfix/add-trigger"

        launch_command("traverse", "-wy")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws
              |
              | Drop unneeded SQL constraints
              o-drop-constraint

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger *
              |
              | Ignore trailing data (amended)
              o-ignore-trailing
            """,
        )

        # Go from hotfix/add-trigger to call-ws which has >1 commit to be squashed
        for _ in range(3):
            launch_command("go", "prev")
        launch_command("squash")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain
            |
            | Call web service
            o-call-ws * (diverged from origin)
              |
              | Drop unneeded SQL constraints
              x-drop-constraint

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger
              |
              | Ignore trailing data (amended)
              o-ignore-trailing
            """,
        )

    def test_traverse_with_merge(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch("develop")
        commit()
        new_branch('mars')
        commit()
        new_branch('snickers')
        commit()
        check_out('mars')
        commit()
        check_out('develop')
        commit()

        body: str = \
            """
            develop
                mars
                    snickers
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("q"))
        launch_command("traverse", "-M")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n", "q"))
        launch_command("traverse", "-M")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("yq"))
        assert_success(
            ["traverse", "--start-from=root", "-M", "--no-edit-merge"],
            """
            Checking out the root branch (develop)... OK

            Checking out mars... OK

              develop
              |
              x-mars *
                |
                x-snickers

            Merge develop into mars? (y, N, q, yq)
            """
        )

    def test_traverse_with_merge_annotation(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch("develop")
        commit()
        new_branch("mars")
        commit()
        new_branch("snickers")
        commit()
        check_out("mars")
        commit()
        check_out("develop")
        commit()

        body: str = """
            develop
                mars update=merge
                    snickers
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("q"))
        launch_command("traverse")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n", "q"))
        launch_command("traverse")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("yq"))
        assert_success(
            ["traverse", "--start-from=root", "--no-edit-merge"],
            """
            Checking out the root branch (develop)... OK

            Checking out mars... OK

              develop
              |
              x-mars *  update=merge
                |
                x-snickers

            Merge develop into mars? (y, N, q, yq)
            """,
        )

    def test_traverse_with_merge_annotation_and_yes_option(self) -> None:
        create_repo()
        new_branch("develop")
        commit()
        new_branch("mars")
        commit()
        new_branch("snickers")
        commit()
        check_out("mars")
        commit()
        check_out("develop")
        commit()

        body: str = """
            develop
                mars update=merge
                    snickers
            """
        rewrite_branch_layout_file(body)

        with overridden_environment(GIT_EDITOR='false'):
            # --yes should imply --no-edit-merge, if it doesn't then the command will fail due to a non-zero exit code from the editor
            launch_command("traverse", "--start-from=root", "--yes"),

        assert_success(
            ["status"],
            """
            develop
            |
            o-mars  update=merge
              |
              o-snickers *
            """,
        )

    def test_traverse_qualifiers_no_push(self) -> None:
        self.setup_standard_tree()

        body: str = \
            """
            develop
            \tallow-ownership-link push=no
            \t\tbuild-chain push=no
            \tcall-ws push=no
            \t\tdrop-constraint push=no
            master
            \thotfix/add-trigger push=no
            \t\tignore-trailing
            """
        rewrite_branch_layout_file(body)

        launch_command("traverse", "-Wy", "--no-push-untracked", "--push-untracked")
        assert_success(
            ["status"],
            """
            develop
            |
            o-allow-ownership-link  push=no (diverged from origin)
            | |
            | o-build-chain  push=no (untracked)
            |
            o-call-ws  push=no (ahead of origin)
              |
              o-drop-constraint  push=no (untracked)

            master
            |
            o-hotfix/add-trigger  push=no (diverged from origin)
              |
              o-ignore-trailing *
            """,
        )

    def test_traverse_qualifiers_no_rebase(self) -> None:
        self.setup_standard_tree()

        body: str = \
            """
            develop
            \tallow-ownership-link rebase=no
            \t\tbuild-chain rebase=no
            \tcall-ws rebase=no
            \t\tdrop-constraint
            master
            \thotfix/add-trigger
            \t\tignore-trailing
            """
        rewrite_branch_layout_file(body)

        launch_command("traverse", "-Wy")
        assert_success(
            ["status"],
            """
            develop
            |
            x-allow-ownership-link  rebase=no
            | |
            | x-build-chain  rebase=no
            |
            o-call-ws  rebase=no
              |
              o-drop-constraint

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing *
            """,
        )

    def test_traverse_qualifiers_no_rebase_no_push(self) -> None:
        self.setup_standard_tree()

        body: str = \
            """
            develop
            \tallow-ownership-link rebase=no push=no
            \t\tbuild-chain rebase=no push=no
            \tcall-ws
            \t\tdrop-constraint rebase=no push=no
            master
            \thotfix/add-trigger
            \t\tignore-trailing
            """
        rewrite_branch_layout_file(body)

        launch_command("traverse", "-Wy")
        assert_success(
            ["status"],
            """
            develop
            |
            x-allow-ownership-link  rebase=no push=no (ahead of origin)
            | |
            | x-build-chain  rebase=no push=no (untracked)
            |
            o-call-ws
              |
              x-drop-constraint  rebase=no push=no (untracked)

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing *
            """,
        )

    def test_traverse_qualifiers_no_slide_out(self) -> None:
        self.setup_standard_tree()

        body: str = \
            """
            develop
            \tallow-ownership-link
            \t\tbuild-chain
            \tcall-ws slide-out=no
            \t\tdrop-constraint
            master
            \thotfix/add-trigger
            \t\tignore-trailing
            """
        rewrite_branch_layout_file(body)
        check_out('develop')
        merge('call-ws')

        launch_command("traverse", "-Wy")
        assert_success(
            ["status"],
            """
            develop *
            |
            o-allow-ownership-link
            | |
            | o-build-chain
            |
            m-call-ws  slide-out=no
              |
              o-drop-constraint

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing
            """,
        )

    def test_traverse_no_managed_branches(self) -> None:
        create_repo()

        expected_error_message = """
          No branches listed in .git/machete. Consider one of:
          * git machete discover
          * git machete edit or edit .git/machete manually
          * git machete github checkout-prs --mine
          * git machete gitlab checkout-mrs --mine"""
        assert_failure(["traverse"], expected_error_message)

    def test_traverse_invalid_flag_values(self) -> None:
        assert_failure(["traverse", "--return-to=dunno-where"],
                       "Invalid value for --return-to flag: dunno-where. Valid values are here, nearest-remaining, stay")
        assert_failure(["traverse", "--squash-merge-detection=lolxd"],
                       "Invalid value for --squash-merge-detection flag: lolxd. Valid values are none, simple, exact")

    def test_traverse_start_from_branch_names(self) -> None:
        """Test the new functionality for --start-from accepting branch names."""
        self.setup_standard_tree()

        # Test starting from a specific branch name
        check_out("develop")
        assert_success(
            ["traverse", "--start-from=call-ws", "-y"],
            """
            Checking out call-ws... OK

            Pushing call-ws to origin...

            Checking out drop-constraint... OK

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws
                |
                x-drop-constraint * (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Rebasing drop-constraint onto call-ws...

            Pushing untracked branch drop-constraint to origin...

            Checking out hotfix/add-trigger... OK

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws
                |
                o-drop-constraint

              master
              |
              o-hotfix/add-trigger * (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Branch hotfix/add-trigger diverged from (and has newer commits than) its remote counterpart origin/hotfix/add-trigger.
            Pushing hotfix/add-trigger with force-with-lease to origin...

            Checking out ignore-trailing... OK

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws
                |
                o-drop-constraint

              master
              |
              o-hotfix/add-trigger
                |
                o-ignore-trailing * (diverged from & older than origin)

            Skipping sync of ignore-trailing with hotfix/add-trigger; ignore-trailing is diverged from (and has older commits than) its remote counterpart

            Branch ignore-trailing diverged from (and has older commits than) its remote counterpart origin/ignore-trailing.
            Resetting branch ignore-trailing to the commit pointed by origin/ignore-trailing...

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws
                |
                o-drop-constraint

              master
              |
              o-hotfix/add-trigger
                |
                o-ignore-trailing *

            Reached branch ignore-trailing which has no successor; nothing left to update
            """
        )

    def test_traverse_start_from_case_insensitive_special_values(self) -> None:
        """Test case-insensitive special values for --start-from and --return-to."""
        self.setup_standard_tree()
        check_out("call-ws")

        # Test case-insensitive "ROOT"
        assert_success(
            ["traverse", "--start-from=ROOT", "--return-to=HERE", "-y"],
            """
            Checking out the root branch (develop)... OK

            Checking out allow-ownership-link... OK

              develop
              |
              x-allow-ownership-link * (ahead of origin)
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
                o-ignore-trailing (diverged from & older than origin)

            Rebasing allow-ownership-link onto develop...

            Branch allow-ownership-link diverged from (and has newer commits than) its remote counterpart origin/allow-ownership-link.
            Pushing allow-ownership-link with force-with-lease to origin...

            Checking out build-chain... OK

              develop
              |
              o-allow-ownership-link
              | |
              | x-build-chain * (untracked)
              |
              o-call-ws (ahead of origin)
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Rebasing build-chain onto allow-ownership-link...

            Pushing untracked branch build-chain to origin...

            Checking out call-ws... OK

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              o-call-ws * (ahead of origin)
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Pushing call-ws to origin...

            Checking out drop-constraint... OK

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              o-call-ws
                |
                x-drop-constraint * (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Rebasing drop-constraint onto call-ws...

            Pushing untracked branch drop-constraint to origin...

            Checking out hotfix/add-trigger... OK

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              o-call-ws
                |
                o-drop-constraint

              master
              |
              o-hotfix/add-trigger * (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Branch hotfix/add-trigger diverged from (and has newer commits than) its remote counterpart origin/hotfix/add-trigger.
            Pushing hotfix/add-trigger with force-with-lease to origin...

            Checking out ignore-trailing... OK

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              o-call-ws
                |
                o-drop-constraint

              master
              |
              o-hotfix/add-trigger
                |
                o-ignore-trailing * (diverged from & older than origin)

            Skipping sync of ignore-trailing with hotfix/add-trigger; ignore-trailing is diverged from (and has older commits than) its remote counterpart

            Branch ignore-trailing diverged from (and has older commits than) its remote counterpart origin/ignore-trailing.
            Resetting branch ignore-trailing to the commit pointed by origin/ignore-trailing...
            Checking out call-ws... OK

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              o-call-ws *
                |
                o-drop-constraint

              master
              |
              o-hotfix/add-trigger
                |
                o-ignore-trailing

            Reached branch ignore-trailing which has no successor; nothing left to update
            Returned to the initial branch call-ws
            """
        )

    def test_traverse_branch_priority_over_special_values(self) -> None:
        """Test that actual branch names take priority over special values when ambiguous."""
        self.setup_standard_tree()

        # Create a branch named "root" to test ambiguity resolution
        check_out("develop")
        new_branch("root")
        commit("root branch commit")

        # Add the "root" branch to the layout
        body: str = \
            """
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
                root
            master
                hotfix/add-trigger
                    ignore-trailing
            """
        rewrite_branch_layout_file(body)

        check_out("develop")

        # When we specify --start-from=root, it should use the actual "root" branch, not the special value
        assert_success(
            ["traverse", "--start-from=root", "-y"],
            """
            Checking out root... OK

            Pushing untracked branch root to origin...

            Checking out hotfix/add-trigger... OK

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws (ahead of origin)
              | |
              | x-drop-constraint (untracked)
              |
              o-root

              master
              |
              o-hotfix/add-trigger * (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Branch hotfix/add-trigger diverged from (and has newer commits than) its remote counterpart origin/hotfix/add-trigger.
            Pushing hotfix/add-trigger with force-with-lease to origin...

            Checking out ignore-trailing... OK

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws (ahead of origin)
              | |
              | x-drop-constraint (untracked)
              |
              o-root

              master
              |
              o-hotfix/add-trigger
                |
                o-ignore-trailing * (diverged from & older than origin)

            Skipping sync of ignore-trailing with hotfix/add-trigger; ignore-trailing is diverged from (and has older commits than) its remote counterpart

            Branch ignore-trailing diverged from (and has older commits than) its remote counterpart origin/ignore-trailing.
            Resetting branch ignore-trailing to the commit pointed by origin/ignore-trailing...

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws (ahead of origin)
              | |
              | x-drop-constraint (untracked)
              |
              o-root

              master
              |
              o-hotfix/add-trigger
                |
                o-ignore-trailing *

            Reached branch ignore-trailing which has no successor; nothing left to update
            """
        )

    def test_traverse_start_from_nonexistent_branch(self) -> None:
        """Test error handling for non-existent branch names."""
        self.setup_standard_tree()
        check_out("develop")

        assert_failure(
            ["traverse", "--start-from=nonexistent-branch"],
            "nonexistent-branch is neither a special value (here, root, first-root), nor a local branch"
        )

    def test_traverse_stop_after_basic(self) -> None:
        """Test basic --stop-after functionality."""
        self.setup_standard_tree()
        check_out("develop")

        # Stop after call-ws, should not process drop-constraint
        assert_success(
            ["traverse", "--stop-after=call-ws", "-y"],
            """
            Checking out allow-ownership-link... OK

              develop
              |
              x-allow-ownership-link * (ahead of origin)
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
                o-ignore-trailing (diverged from & older than origin)

            Rebasing allow-ownership-link onto develop...

            Branch allow-ownership-link diverged from (and has newer commits than) its remote counterpart origin/allow-ownership-link.
            Pushing allow-ownership-link with force-with-lease to origin...

            Checking out build-chain... OK

              develop
              |
              o-allow-ownership-link
              | |
              | x-build-chain * (untracked)
              |
              o-call-ws (ahead of origin)
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Rebasing build-chain onto allow-ownership-link...

            Pushing untracked branch build-chain to origin...

            Checking out call-ws... OK

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              o-call-ws * (ahead of origin)
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Pushing call-ws to origin...

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              o-call-ws *
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            No successor of call-ws needs to be slid out or synced with upstream branch or remote; nothing left to update
            """
        )

    def test_traverse_stop_after_with_start_from(self) -> None:
        """Test --stop-after with --start-from."""
        self.setup_standard_tree()
        check_out("develop")

        # Start from allow-ownership-link and stop after call-ws
        assert_success(
            ["traverse", "--start-from=allow-ownership-link", "--stop-after=call-ws", "-y"],
            """
            Checking out allow-ownership-link... OK

            Rebasing allow-ownership-link onto develop...

            Branch allow-ownership-link diverged from (and has newer commits than) its remote counterpart origin/allow-ownership-link.
            Pushing allow-ownership-link with force-with-lease to origin...

            Checking out build-chain... OK

              develop
              |
              o-allow-ownership-link
              | |
              | x-build-chain * (untracked)
              |
              o-call-ws (ahead of origin)
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Rebasing build-chain onto allow-ownership-link...

            Pushing untracked branch build-chain to origin...

            Checking out call-ws... OK

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              o-call-ws * (ahead of origin)
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Pushing call-ws to origin...

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              o-call-ws *
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            No successor of call-ws needs to be slid out or synced with upstream branch or remote; nothing left to update
            """
        )

    def test_traverse_stop_after_unmanaged_branch(self) -> None:
        self.setup_standard_tree()
        check_out("develop")

        # Test unmanaged branch
        new_branch("unmanaged-branch")
        commit("unmanaged commit")
        check_out("develop")

        assert_failure(
            ["traverse", "--stop-after=unmanaged-branch"],
            "Branch unmanaged-branch not found in the tree of branch dependencies.\n"
            "Use git machete add unmanaged-branch or git machete edit."
        )

    def test_traverse_stop_after_when_branch_is_slid_out(self) -> None:
        """Test --stop-after when the target branch gets slid out during traversal."""
        self.setup_standard_tree()

        # Create a scenario where call-ws is merged and will be slid out
        check_out("call-ws")
        check_out("develop")
        # Merge call-ws into develop to make it appear merged
        merge("call-ws")
        push()

        # Now traverse with --stop-after=call-ws - it should stop even though call-ws gets slid out
        # This test demonstrates the bug: traverse continues to drop-constraint instead of stopping after call-ws
        assert_success(
            ["traverse", "--stop-after=call-ws", "-y"],
            """
            Checking out allow-ownership-link... OK

              develop
              |
              x-allow-ownership-link * (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              m-call-ws (ahead of origin)
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Rebasing allow-ownership-link onto develop...

            Branch allow-ownership-link diverged from (and has newer commits than) its remote counterpart origin/allow-ownership-link.
            Pushing allow-ownership-link with force-with-lease to origin...

            Checking out build-chain... OK

              develop
              |
              o-allow-ownership-link
              | |
              | x-build-chain * (untracked)
              |
              m-call-ws (ahead of origin)
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Rebasing build-chain onto allow-ownership-link...

            Pushing untracked branch build-chain to origin...

            Checking out call-ws... OK

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              m-call-ws * (ahead of origin)
                |
                x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            Branch call-ws is merged into develop. Sliding call-ws out of the tree of branch dependencies...

              develop
              |
              o-allow-ownership-link
              | |
              | o-build-chain
              |
              x-drop-constraint (untracked)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing (diverged from & older than origin)

            No successor of call-ws needs to be slid out or synced with upstream branch or remote; nothing left to update
            """
        )

    def test_traverse_removes_current_directory(self) -> None:
        (local_path, _) = create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch("with-directory")
        add_file_and_commit(file_path="directory/file.txt")
        check_out("master")
        new_branch("without-directory")
        commit()
        check_out("master")
        commit()
        check_out("with-directory")

        body: str = \
            """
            master
              with-directory
              without-directory
            """
        rewrite_branch_layout_file(body)

        os.chdir("directory")

        common_expected_output = """
            Rebasing with-directory onto master...

            Pushing untracked branch with-directory to origin...

            Checking out without-directory... OK

              master (untracked)
              |
              o-with-directory
              |
              x-without-directory * (untracked)

            Rebasing without-directory onto master...

            Pushing untracked branch without-directory to origin...

              master (untracked)
              |
              o-with-directory
              |
              o-without-directory *

            Reached branch without-directory which has no successor; nothing left to update
            """
        if get_git_version() >= (2, 35, 0):
            # See https://github.com/git/git/blob/master/Documentation/RelNotes/2.35.0.txt#L81 for the fix
            assert_success(
                ["traverse", "-y"],
                common_expected_output
            )
            assert os.path.split(os.getcwd())[-1] == "directory"
        else:
            assert_success(
                ["traverse", "-y"],
                common_expected_output +
                f"Warn: current directory {local_path}/directory no longer exists, " +
                f"the nearest existing parent directory is {local_path}\n"
            )
            assert os.path.split(os.getcwd())[-1] != "directory"

    def test_traverse_reset_keep_failing(self) -> None:
        create_repo_with_remote()
        new_branch("master")
        add_file_and_commit(file_path="foo.txt", file_content="1")
        sleep(1)
        write_to_file(file_path="foo.txt", file_content="2")
        amend_commit()
        push()
        reset_to("HEAD@{1}")  # noqa: FS003
        write_to_file(file_path="foo.txt", file_content="3")

        rewrite_branch_layout_file("master")

        assert_failure(
            ["traverse", "--fetch", "-y", "--debug"],
            "Cannot perform git reset --keep origin/master. This is most likely caused by local uncommitted changes.",
            expected_type=UnderlyingGitException
        )

    def test_traverse_with_stop_for_edit(self, mocker: MockerFixture) -> None:

        create_repo()
        new_branch("branch-0")
        commit()
        new_branch("branch-1")
        commit()
        check_out("branch-0")
        commit()

        rewrite_branch_layout_file("branch-0\n\tbranch-1")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '1s/^pick /edit /'"):
            launch_command("traverse")

        assert_success(
            ["status"],
            """
            branch-0
            |
            x-REBASING branch-1 *
            """
        )

    def test_reset_to_remote_after_rebase(self) -> None:
        """Very unlikely case; can happen only in case of divergence of clocks between local and remote
        (which is simulated in this test)."""
        create_repo_with_remote()
        new_branch("branch-0")
        commit()
        push()
        new_branch("branch-1")
        commit()
        push()
        check_out("branch-0")
        commit()

        rewrite_branch_layout_file("branch-0\n\tbranch-1")

        with fixed_author_and_committer_date_in_past():
            assert_success(
                ["traverse", "-y"],
                """
            Pushing branch-0 to origin...

            Checking out branch-1... OK

              branch-0
              |
              x-branch-1 *

            Rebasing branch-1 onto branch-0...

            Branch branch-1 diverged from (and has older commits than) its remote counterpart origin/branch-1.
            Resetting branch branch-1 to the commit pointed by origin/branch-1...

              branch-0
              |
              x-branch-1 *

            Reached branch branch-1 which has no successor; nothing left to update
            """
            )

    def test_traverse_quit_on_pushing_untracked(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()
        new_branch("master")
        commit()
        rewrite_branch_layout_file("master")
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(
            ["traverse"],
            "Push untracked branch master to origin? (y, N, q, yq)\n"
        )

    def test_traverse_multiple_remotes(self, mocker: MockerFixture) -> None:
        create_repo()
        origin_1_remote_path = create_repo("remote-1", bare=True, switch_dir_to_new_repo=False)
        origin_2_remote_path = create_repo("remote-2", bare=True, switch_dir_to_new_repo=False)
        add_remote("origin-1", origin_1_remote_path)
        add_remote("origin-2", origin_2_remote_path)

        new_branch("master")
        commit()
        rewrite_branch_layout_file("master")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("xd"))
        assert_success(
            ["traverse", "--fetch"],
            """
            Fetching origin-1...
            Fetching origin-2...

            Branch master is untracked and there's no origin remote.
            [1] origin-1
            [2] origin-2
            Select number 1..2 to specify the destination remote repository, or 'n' to skip this branch, or 'q' to quit the traverse:

              master * (untracked)

            Reached branch master which has no successor; nothing left to update
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("1", "o", "2", "yq"))
        set_git_config_key("machete.traverse.fetch.origin-2", "false")
        assert_success(
            ["traverse", "--fetch"],
            """
            Fetching origin-1...

            Branch master is untracked and there's no origin remote.
            [1] origin-1
            [2] origin-2
            Select number 1..2 to specify the destination remote repository, or 'n' to skip this branch, or 'q' to quit the traverse:
            Push untracked branch master to origin-1? (y, N, q, yq, o[ther-remote])
            [1] origin-1
            [2] origin-2
            Select number 1..2 to specify the destination remote repository, or 'n' to skip this branch, or 'q' to quit the traverse:
            Push untracked branch master to origin-2? (y, N, q, yq, o[ther-remote])
            """
        )

    def test_traverse_yellow_edges(self, mocker: MockerFixture) -> None:
        E = FullTerminalAnsiOutputCodes
        self.patch_symbol(mocker, "git_machete.utils.is_stdout_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_stderr_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_terminal_fully_fledged", lambda: True)

        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        new_branch("feature-1")
        commit()
        check_out("develop")
        new_branch("feature-2")
        commit()

        body: str = \
            """
            master
                feature-1
                feature-2
            """
        rewrite_branch_layout_file(body)

        ok = f"{E.GREEN}{E.BOLD}OK{E.ENDC_BOLD_DIM}{E.ENDC}"
        pc = f"({E.GREEN}y{E.ENDC}, {E.RED}N{E.ENDC}, {E.RED}q{E.ENDC}, {E.GREEN}y{E.ENDC}{E.RED}q{E.ENDC})"

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n", "n"))
        assert_success(
            ["traverse", "-w"],
            textwrap.dedent(f"""\
            Checking out the root branch ({E.BOLD}master{E.ENDC_BOLD_DIM})... {ok}

            Checking out {E.BOLD}feature-1{E.ENDC_BOLD_DIM}... {ok}

              {E.BOLD}master{E.ENDC_BOLD_DIM}
              {E.YELLOW}│{E.ENDC}
              {E.YELLOW}├─{E.ENDC}{E.BOLD}{E.UNDERLINE}feature-1{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}
              {E.YELLOW}│{E.ENDC}
              {E.YELLOW}└─{E.ENDC}{E.BOLD}feature-2{E.ENDC_BOLD_DIM}

            {E.ORANGE}Warn: {E.ENDC}yellow edges indicate that fork points for {E.BOLD}feature-1{E.ENDC_BOLD_DIM}, {E.BOLD}feature-2{E.ENDC_BOLD_DIM} are probably incorrectly inferred,
            or that some extra branch should be added between each of these branches and its parent.

            Run {E.UNDERLINE}git machete status --list-commits{E.ENDC_UNDERLINE} or {E.UNDERLINE}git machete status --list-commits-with-hashes{E.ENDC_UNDERLINE} to see more details.

            Rebase {E.BOLD}feature-1{E.ENDC_BOLD_DIM} onto {E.BOLD}master{E.ENDC_BOLD_DIM}? {pc}

            Checking out {E.BOLD}feature-2{E.ENDC_BOLD_DIM}... {ok}

              {E.BOLD}master{E.ENDC_BOLD_DIM}
              {E.YELLOW}│{E.ENDC}
              {E.YELLOW}├─{E.ENDC}{E.BOLD}feature-1{E.ENDC_BOLD_DIM}
              {E.YELLOW}│{E.ENDC}
              {E.YELLOW}└─{E.ENDC}{E.BOLD}{E.UNDERLINE}feature-2{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}


            Rebase {E.BOLD}feature-2{E.ENDC_BOLD_DIM} onto {E.BOLD}master{E.ENDC_BOLD_DIM}? {pc}

              {E.BOLD}master{E.ENDC_BOLD_DIM}
              {E.YELLOW}│{E.ENDC}
              {E.YELLOW}├─{E.ENDC}{E.BOLD}feature-1{E.ENDC_BOLD_DIM}
              {E.YELLOW}│{E.ENDC}
              {E.YELLOW}└─{E.ENDC}{E.BOLD}{E.UNDERLINE}feature-2{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}


            Reached branch {E.BOLD}feature-2{E.ENDC_BOLD_DIM} which has no successor; nothing left to update
            Returned to the initial branch {E.BOLD}feature-2{E.ENDC_BOLD_DIM}
            """)
        )

    # The expected error message includes `--empty=drop` which is only passed on git >= 2.26.0.
    @pytest.mark.skipif(get_git_version() < (2, 26, 0), reason="--empty=drop is only passed to git rebase since git 2.26.0")
    def test_traverse_rebase_conflict(self) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch("master")
            add_file_and_commit("file.txt", "base content\n", "Base commit")
            new_branch("feature")
            add_file_and_commit("file.txt", "feature content\n", "Feature commit")
            check_out("master")
            add_file_and_commit("file.txt", "master content\n", "Master commit")
        check_out("feature")

        rewrite_branch_layout_file("master\n\tfeature")

        assert_failure(
            ["traverse", "-y"],
            "git -c log.showSignature=false rebase --empty=drop"
            " --onto refs/heads/master 77b81e64de792099dad58d67756b66cda9e80aa7 feature returned 1",
            expected_type=UnderlyingGitException,
            expected_output="""
            Rebasing feature onto master...
            """
        )

    def test_traverse_behind_remote_with_red_edge(self, mocker: MockerFixture) -> None:
        E = FullTerminalAnsiOutputCodes
        self.patch_symbol(mocker, "git_machete.utils.is_stdout_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_stderr_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_terminal_fully_fledged", lambda: True)

        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        commit()
        push()
        reset_to("HEAD~")
        check_out("master")
        commit()
        push()
        check_out("feature")

        rewrite_branch_layout_file("master\n\tfeature")

        assert_success(
            ["traverse", "-y"],
            textwrap.dedent(f"""\
            Skipping sync of {E.BOLD}feature{E.ENDC_BOLD_DIM} with {E.BOLD}master{E.ENDC_BOLD_DIM}; {E.BOLD}feature{E.ENDC_BOLD_DIM} is behind its remote counterpart

            Branch {E.BOLD}feature{E.ENDC_BOLD_DIM} is behind its remote counterpart {E.BOLD}origin/feature{E.ENDC_BOLD_DIM}.
            Pulling {E.BOLD}feature{E.ENDC_BOLD_DIM} (fast-forward only) from {E.BOLD}origin{E.ENDC_BOLD_DIM}...

              {E.BOLD}master{E.ENDC_BOLD_DIM}
              {E.RED}│{E.ENDC}
              {E.RED}└─{E.ENDC}{E.BOLD}{E.UNDERLINE}feature{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}

            Reached branch {E.BOLD}feature{E.ENDC_BOLD_DIM} which has no successor; nothing left to update
            """)
        )

    def test_traverse_diverged_from_and_older_with_red_edge(self, mocker: MockerFixture) -> None:
        E = FullTerminalAnsiOutputCodes
        self.patch_symbol(mocker, "git_machete.utils.is_stdout_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_stderr_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_terminal_fully_fledged", lambda: True)

        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        push()
        with fixed_author_and_committer_date_in_past():
            amend_commit()
        check_out("master")
        commit()
        push()
        check_out("feature")

        rewrite_branch_layout_file("master\n\tfeature")

        assert_success(
            ["traverse", "-y"],
            textwrap.dedent(f"""\
            Skipping sync of {E.BOLD}feature{E.ENDC_BOLD_DIM} with {E.BOLD}master{E.ENDC_BOLD_DIM}; {E.BOLD}feature{E.ENDC_BOLD_DIM} is diverged from (and has older commits than) its remote counterpart

            Branch {E.BOLD}feature{E.ENDC_BOLD_DIM} diverged from (and has older commits than) its remote counterpart {E.BOLD}origin/feature{E.ENDC_BOLD_DIM}.
            Resetting branch {E.BOLD}feature{E.ENDC_BOLD_DIM} to the commit pointed by {E.BOLD}origin/feature{E.ENDC_BOLD_DIM}...

              {E.BOLD}master{E.ENDC_BOLD_DIM}
              {E.RED}│{E.ENDC}
              {E.RED}└─{E.ENDC}{E.BOLD}{E.UNDERLINE}feature{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}

            Reached branch {E.BOLD}feature{E.ENDC_BOLD_DIM} which has no successor; nothing left to update
            """)
        )
