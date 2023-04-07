from .mockers import (GitRepositorySandbox, assert_command, launch_command,
                      rewrite_definition_file)


class TestAnno:

    def setup_method(self) -> None:
        self.repo_sandbox = GitRepositorySandbox()

        (
            self.repo_sandbox
            # Create the remote and sandbox repos, chdir into sandbox repo
            .new_repo(self.repo_sandbox.remote_path, "--bare")
            .new_repo(self.repo_sandbox.local_path)
            .execute(f"git remote add origin {self.repo_sandbox.remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
        )

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
        assert_command(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature (untracked)
            """,
        )

        launch_command('anno', '-b=feature', 'Custom annotation for `feature` branch')
        assert_command(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch (untracked)
            """,
        )

        launch_command('anno', '-b=refs/heads/feature', 'Custom annotation for `feature` branch')
        assert_command(
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
        assert_command(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch rebase=no push=no (untracked)
            """,
        )
        launch_command('anno', '-b=refs/heads/feature', 'Custom annotation for `feature` branch')
        assert_command(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch (untracked)
            """,
        )
