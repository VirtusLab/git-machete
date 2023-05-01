from .base_test import BaseTest
from .mockers import assert_success, launch_command, rewrite_definition_file


class TestAnno(BaseTest):

    def test_anno(self) -> None:
        """
        Verify behaviour of a 'git machete anno' command.
        """

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
        rewrite_definition_file(body)

        # Test `git machete anno` without providing the branch name
        launch_command('anno', 'Custom annotation for `develop` branch')
        assert_success(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature (untracked)
            """,
        )

        launch_command('anno', '-b=feature', 'Custom annotation for `feature` branch')
        assert_success(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch (untracked)
            """,
        )

        launch_command('anno', '-b=refs/heads/feature', 'Custom annotation for `feature` branch')
        assert_success(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch (untracked)
            """,
        )

        # check if annotation qualifiers are parsed correctly and that they can be overwritten by `git machete anno`
        launch_command('anno', '-b=refs/heads/feature', 'push=no Custom annotation for `feature` branch rebase=no')
        assert_success(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch rebase=no push=no (untracked)
            """,
        )
        launch_command('anno', '-b=refs/heads/feature', 'Custom annotation for `feature` branch')
        assert_success(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch (untracked)
            """,
        )

        assert_success(
            ['anno'],
            'Custom annotation for `develop` branch\n'
        )

        assert_success(
            ['anno', '-b', 'feature'],
            'Custom annotation for `feature` branch\n'
        )

        assert_success(
            ['anno', '-b', 'feature', ''],
            ""
        )

        assert_success(
            ['anno', '-b', 'feature'],
            ""
        )
