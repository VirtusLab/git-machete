import subprocess
import textwrap

from tests.base_test import BaseTest
from tests.cli_runner import assert_failure, assert_success, rewrite_branch_layout_file
from tests.git_repository import check_out, commit, create_repo, create_repo_with_remote, get_local_branches, new_branch, push
from tests.shell import popen


class TestRename(BaseTest):

    def test_rename_current_branch(self) -> None:
        """Renaming current branch updates git and the branch layout file."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        new_branch("feature-child")
        commit()
        check_out("feature")

        rewrite_branch_layout_file(
            """
            master
              feature
                feature-child
            """
        )

        assert_success(
            ["rename", "feature-renamed"],
            "Renamed branch feature to feature-renamed\n"
        )

        assert "feature-renamed" in get_local_branches()
        assert "feature" not in get_local_branches()
        assert popen("git symbolic-ref --short HEAD") == "feature-renamed"

        assert_success(
            ["status"],
            """
            master
            |
            o-feature-renamed *
              |
              o-feature-child
            """
        )

    def test_rename_with_branch_flag(self) -> None:
        """Renaming a non-current branch via -b leaves HEAD on current branch."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        check_out("master")

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        assert_success(
            ["rename", "-b", "feature", "feature-new"],
            "Renamed branch feature to feature-new\n"
        )

        assert popen("git symbolic-ref --short HEAD") == "master"
        assert "feature-new" in get_local_branches()
        assert "feature" not in get_local_branches()

        assert_success(
            ["status"],
            """
            master *
            |
            o-feature-new
            """
        )

    def test_rename_root_branch(self) -> None:
        """Renaming a root branch keeps it as root in the layout file."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        check_out("master")

        rewrite_branch_layout_file(
            """
            master
              develop
            """
        )

        assert_success(
            ["rename", "main"],
            "Renamed branch master to main\n"
        )

        assert "main" in get_local_branches()
        assert "master" not in get_local_branches()

        assert_success(
            ["status"],
            """
            main *
            |
            o-develop
            """
        )

    def test_rename_preserves_children(self) -> None:
        """Renaming a middle branch preserves its parent and both children."""
        create_repo()
        new_branch("root")
        commit()
        new_branch("middle")
        commit()
        new_branch("child-a")
        commit()
        check_out("middle")
        new_branch("child-b")
        commit()
        check_out("middle")

        rewrite_branch_layout_file(
            """
            root
              middle
                child-a
                child-b
            """
        )

        assert_success(
            ["rename", "middle-renamed"],
            "Renamed branch middle to middle-renamed\n"
        )

        assert_success(
            ["status"],
            """
            root
            |
            o-middle-renamed *
              |
              o-child-a
              |
              o-child-b
            """
        )

    def test_rename_preserves_annotation(self) -> None:
        """Renaming a branch with an annotation carries the annotation over."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        check_out("feature")

        rewrite_branch_layout_file(
            """
            master
              feature  some annotation
            """
        )

        assert_success(
            ["rename", "feature-v2"],
            "Renamed branch feature to feature-v2\n"
        )

        assert_success(
            ["anno", "-b", "feature-v2"],
            "some annotation\n"
        )

    def test_rename_same_name_fails(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        check_out("feature")

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        assert_failure(
            ["rename", "feature"],
            "Branch is already named feature"
        )

    def test_rename_to_existing_branch_fails(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        check_out("feature")

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        assert_failure(
            ["rename", "master"],
            "Branch master already exists"
        )

    def test_rename_unmanaged_branch_fails(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("unmanaged")
        commit()
        check_out("unmanaged")

        rewrite_branch_layout_file("master\n")

        assert_failure(
            ["rename", "something"],
            "Branch unmanaged not found in the tree of branch dependencies.\n"
            "Use git machete add unmanaged or git machete edit."
        )

    def test_rename_repoint_tracking_remote_exists(self) -> None:
        """--repoint-tracking sets upstream to origin/<new-name> when it exists."""
        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        push()  # feature -> origin/feature, sets upstream
        check_out("feature")

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        # Push the new name to the remote so origin/feature-new exists
        popen("git push origin feature:feature-new")

        assert_success(
            ["rename", "--repoint-tracking", "feature-new"],
            textwrap.dedent("""\
                Repointed tracking to origin/feature-new
                Renamed branch feature to feature-new
            """)
        )

        assert "feature-new" in get_local_branches()
        assert "feature" not in get_local_branches()
        # Tracking merge ref now points to new name
        upstream_merge = popen("git config branch.feature-new.merge")
        assert upstream_merge == "refs/heads/feature-new"

    def test_rename_repoint_tracking_remote_missing(self) -> None:
        """--repoint-tracking unsets upstream when origin/<new-name> does not exist."""
        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        push()  # feature tracks origin/feature
        check_out("feature")

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        # Do NOT push feature-new to remote, so origin/feature-new is absent
        assert_success(
            ["rename", "--repoint-tracking", "feature-new"],
            textwrap.dedent("""\
                Unset tracking (remote branch origin/feature-new does not exist)
                Renamed branch feature to feature-new
            """)
        )

        assert "feature-new" in get_local_branches()
        assert "feature" not in get_local_branches()
        # Upstream config is gone
        result = subprocess.call("git config branch.feature-new.merge", shell=True)
        assert result != 0, "Expected branch.feature-new.merge to be unset after --repoint-tracking"

    def test_rename_repoint_tracking_no_remote_configured(self) -> None:
        """--repoint-tracking is a no-op (no message) when the branch has no remote configured."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        check_out("feature")

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        # No remote exists, so there is no strict remote for the branch
        assert_success(
            ["rename", "--repoint-tracking", "feature-new"],
            "Renamed branch feature to feature-new\n"
        )

        assert "feature-new" in get_local_branches()
        assert "feature" not in get_local_branches()

    def test_rename_without_repoint_tracking_keeps_old_remote(self) -> None:
        """Without --repoint-tracking the branch still tracks origin/<old-name>."""
        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()
        push()  # feature tracks origin/feature
        check_out("feature")

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        assert_success(
            ["rename", "feature-new"],
            "Renamed branch feature to feature-new\n"
        )

        # git branch -m moves the tracking config but keeps merge pointing to old name
        upstream_merge = popen("git config branch.feature-new.merge")
        assert upstream_merge == "refs/heads/feature", \
            "Without --repoint-tracking, merge config should still reference the old remote branch name"
