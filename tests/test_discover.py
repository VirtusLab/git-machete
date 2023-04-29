from .base_test import BaseTest
from .mockers import assert_command, launch_command, rewrite_definition_file


class TestDiscover(BaseTest):

    def test_discover(self) -> None:
        (
            self.repo_sandbox
                .new_branch('master')
                .commit()
                .push()
                .new_branch('feature1')
                .commit()
                .new_branch('feature2')
                .commit()
                .check_out("master")
                .new_branch('feature3')
                .commit()
                .push()
                .new_branch('feature4')
                .commit()
        )

        body: str = \
            """
            master
            feature1
            feature2 annotation
            feature3 annotation rebase=no push=no
            """
        rewrite_definition_file(body)
        launch_command('discover', '-y')
        expected_status_output = (
            """
            master
            |
            o-feature1 (untracked)
            | |
            | o-feature2 (untracked)
            |
            o-feature3  rebase=no push=no
              |
              o-feature4 * (untracked)
            """
        )
        assert_command(['status'], expected_status_output)

        launch_command('discover', '--roots=feature1,master', '-y')
        expected_status_output = (
            """
            feature1 (untracked)
            |
            o-feature2 (untracked)

            master
            |
            o-feature3  rebase=no push=no
              |
              o-feature4 * (untracked)
            """
        )
