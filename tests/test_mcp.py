"""Tests for the MCP server (git_machete/mcp_server.py)."""

import io
import json
import textwrap
from typing import Any, Dict, List, Optional, cast

import pytest
from pytest_mock import MockerFixture

from git_machete import utils
from git_machete.git_operations import GitContext
from git_machete.mcp_server import _TOOLS, _dispatch_tool

from .base_test import BaseTest
from .mockers import (fixed_author_and_committer_date_in_past, launch_command,
                      overridden_environment, rewrite_branch_layout_file)
from .mockers_code_hosting import mock_from_url
from .mockers_git_repository import (add_remote, check_out, commit,
                                     create_repo, create_repo_with_remote,
                                     delete_remote_branch, get_commit_hash,
                                     get_current_commit_hash, new_branch, push)
from .mockers_github import (MockGitHubAPIState,
                             mock_github_token_for_domain_fake,
                             mock_github_token_for_domain_none, mock_pr_json)
from .mockers_github import mock_urlopen as mock_github_urlopen
from .mockers_gitlab import (MockGitLabAPIState,
                             mock_gitlab_token_for_domain_fake, mock_mr_json)
from .mockers_gitlab import mock_urlopen as mock_gitlab_urlopen


def _init_messages() -> List[Dict[str, Any]]:
    return [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.0.0"},
        }},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    ]


def _tool_call(
    request_id: int,
    name: str,
    arguments: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments if arguments is not None else {}},
    }


def _mcp_responses_from_launch_output(output: str) -> List[Dict[str, Any]]:
    return [
        json.loads(line)
        for line in output.strip().splitlines()
        if line.strip()
    ]


def _result(responses: List[Dict[str, Any]], index: int) -> Dict[str, Any]:
    """JSON-RPC result for the response at *index* (0 = initialize, 1+ = tool calls)."""
    return cast(Dict[str, Any], responses[index]["result"])


def _setup_branch_tree() -> None:
    """Create a repo with master -> develop -> feature layout."""
    create_repo()
    new_branch("master")
    commit()
    new_branch("develop")
    commit("develop commit")
    new_branch("feature")
    commit("feature commit")
    check_out("develop")
    rewrite_branch_layout_file("master\n\tdevelop\n\t\tfeature\n")


def _github_api_state_for_restack_pr() -> MockGitHubAPIState:
    body = textwrap.dedent('''
        <!-- start git-machete generated -->

        # Based on PR #14

        <!-- end git-machete generated -->
        # Summary''')[1:]
    return MockGitHubAPIState.with_prs(
        mock_pr_json(head='feature_1', base='develop', number=14, draft=True),
        mock_pr_json(head='feature', base='develop', number=15, body=body),
        mock_pr_json(head='multiple-pr-branch', base='develop', number=16),
        mock_pr_json(head='multiple-pr-branch', base='feature', number=17),
    )


class TestMcp(BaseTest):

    def _run_session(
            self,
            mocker: MockerFixture,
            *messages_after_handshake: Dict[str, Any],
            include_handshake: bool = True,
    ) -> List[Dict[str, Any]]:
        if include_handshake:
            messages = [*_init_messages(), *messages_after_handshake]
        else:
            messages = list(messages_after_handshake)
        stdin_text = "\n".join(json.dumps(m) for m in messages) + "\n"
        self.patch_symbol(mocker, "sys.stdin", io.StringIO(stdin_text))
        output = launch_command("mcp")
        return _mcp_responses_from_launch_output(output)

    def test_initialize(self, mocker: MockerFixture) -> None:
        responses = self._run_session(
            mocker,
        )
        assert len(responses) == 1
        r = responses[0]
        assert r["id"] == 0
        assert r["result"]["protocolVersion"] == "2024-11-05"
        assert "tools" in r["result"]["capabilities"]
        assert r["result"]["serverInfo"]["name"] == "git-machete"

    def test_tools_list(self, mocker: MockerFixture) -> None:
        responses = self._run_session(
            mocker,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        tools = responses[1]["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        assert tool_names == {t["name"] for t in _TOOLS}
        assert [t["name"] for t in tools] == sorted(t["name"] for t in tools)
        for tool in tools:
            assert "description" in tool
            assert "inputSchema" in tool

    def test_ping(self, mocker: MockerFixture) -> None:
        responses = self._run_session(
            mocker,
            {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
        )
        assert responses[1]["result"] == {}

    def test_unknown_method(self, mocker: MockerFixture) -> None:
        responses = self._run_session(
            mocker,
            {"jsonrpc": "2.0", "id": 1, "method": "no/such/method", "params": {}},
            include_handshake=False,
        )
        assert responses[0]["error"]["code"] == -32601

    def test_unknown_tool(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch("master")
        commit()
        responses = self._run_session(
            mocker,
            _tool_call(1, "nonexistent"),
        )
        assert "error" in responses[1]

    def test_parse_error(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, "sys.stdin", io.StringIO("this is not json\n"))
        responses = _mcp_responses_from_launch_output(launch_command("mcp"))
        assert responses[0]["error"]["code"] == -32700

    def test_empty_resources_and_prompts(self, mocker: MockerFixture) -> None:
        responses = self._run_session(
            mocker,
            {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "prompts/list", "params": {}},
        )
        assert responses[1]["result"] == {"resources": []}
        assert responses[2]["result"] == {"prompts": []}

    def test_notification_gets_no_response(self, mocker: MockerFixture) -> None:
        responses = self._run_session(
            mocker,
            {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}},
            include_handshake=False,
        )
        assert len(responses) == 0

    def test_skips_blank_lines_between_messages(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch("master")
        commit()
        rewrite_branch_layout_file("master\n")
        init = _init_messages()
        chunks = [
            json.dumps(init[0]) + "\n",
            "\n",
            json.dumps(init[1]) + "\n",
            "\n",
            json.dumps(_tool_call(1, "machete_status")) + "\n",
        ]
        self.patch_symbol(mocker, "sys.stdin", io.StringIO("".join(chunks)))
        responses = _mcp_responses_from_launch_output(launch_command("mcp"))
        assert len(responses) == 2
        assert not responses[1]["result"]["isError"]

    def test_dispatch_tool_unknown_name_raises(self) -> None:
        """`_dispatch_tool` must reject names not handled in its chain (defensive)."""
        create_repo()
        new_branch("master")
        commit()
        git = GitContext()
        with pytest.raises(ValueError, match="Unknown tool"):
            _dispatch_tool("not_registered_machete_tool", {}, git)

    def test_session_branch_tree_introspection_and_error_recovery(self, mocker: MockerFixture) -> None:
        _setup_branch_tree()
        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_status", {"list_commits": True}),
            _tool_call(3, "machete_status", {"list_commits_with_hashes": True}),
            _tool_call(4, "machete_show", {"direction": "up", "branch": "develop"}),
            _tool_call(5, "machete_show", {"direction": "down", "branch": "master"}),
            _tool_call(6, "machete_file"),
            _tool_call(7, "machete_log", {"branch": "develop"}),
            _tool_call(8, "machete_diff", {"branch": "develop", "stat": True}),
            _tool_call(9, "machete_fork_point", {"branch": "develop"}),
            _tool_call(10, "machete_show", {"direction": "current"}),
            _tool_call(11, "machete_show", {"direction": "up", "branch": "master"}),
            _tool_call(12, "machete_status"),
        )
        assert len(responses) == 13
        for i in range(1, 11):
            assert not _result(responses, i)["isError"], i
        fork_point_text = _result(responses, 9)["content"][0]["text"].strip()
        assert len(fork_point_text) == 40
        assert _result(responses, 11)["isError"]
        assert not _result(responses, 12)["isError"]
        text12 = _result(responses, 12)["content"][0]["text"]
        assert "develop" in text12

    def test_session_discover_anno_status_file_and_globals(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("my-feature")
        commit()
        check_out("master")

        run_cmd_before = utils._run_cmd

        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_discover"),
            _tool_call(2, "machete_status"),
            _tool_call(3, "machete_anno", {
                "branch": "my-feature",
                "annotation_text": "via-mcp",
            }),
            _tool_call(4, "machete_status"),
            _tool_call(5, "machete_file"),
        )
        assert len(responses) == 6
        for i in (1, 2, 3, 4, 5):
            assert not _result(responses, i)["isError"], i
        assert "master" in _result(responses, 1)["content"][0]["text"]
        assert "via-mcp" in _result(responses, 4)["content"][0]["text"]
        layout = _result(responses, 5)["content"][0]["text"].strip()
        with open(layout, encoding="utf-8") as f:
            assert "my-feature" in f.read()

        assert utils._run_cmd is run_cmd_before

    def test_session_machete_add_implicit_branch(self, mocker: MockerFixture) -> None:
        """`machete_add` without `branch` adds the checked-out branch (covers default-branch path)."""
        create_repo()
        new_branch("master")
        commit()
        rewrite_branch_layout_file("master\n")
        new_branch("feature-x")
        commit()
        check_out("feature-x")
        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_add", {"onto": "master"}),
            _tool_call(3, "machete_status"),
        )
        assert len(responses) == 4
        for i in (1, 2, 3):
            assert not _result(responses, i)["isError"], i
        assert "feature-x" in _result(responses, 3)["content"][0]["text"]

    def test_session_interleaved_anno_update_slide_file_log(self, mocker: MockerFixture) -> None:
        """Read-only status interleaved with anno, update, slide-out."""
        _setup_branch_tree()
        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_anno", {"annotation_text": "WIP", "branch": "develop"}),
            _tool_call(3, "machete_status"),
            _tool_call(4, "machete_update"),
            _tool_call(5, "machete_status"),
            _tool_call(6, "machete_slide_out", {"branches": ["feature"]}),
            _tool_call(7, "machete_status"),
            _tool_call(8, "machete_file"),
            _tool_call(9, "machete_log", {"branch": "develop"}),
        )
        assert len(responses) == 10
        for i in range(1, 10):
            assert not _result(responses, i)["isError"], i
        assert "WIP" in _result(responses, 3)["content"][0]["text"]
        t7 = _result(responses, 7)["content"][0]["text"]
        assert "feature" not in t7
        assert "develop" in t7

    def test_session_feature_go_update_status(self, mocker: MockerFixture) -> None:
        _setup_branch_tree()
        check_out("feature")
        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_go", {"direction": "up"}),
            _tool_call(3, "machete_status"),
            _tool_call(4, "machete_update"),
            _tool_call(5, "machete_status"),
        )
        assert len(responses) == 6
        for i in range(1, 6):
            assert not _result(responses, i)["isError"], i
        assert "develop" in _result(responses, 2)["content"][0]["text"]

    def test_session_advance_status(self, mocker: MockerFixture) -> None:
        """Advance fast-forwards root onto its single green downstream, then status."""
        create_repo()
        new_branch("root")
        commit("root")
        new_branch("level-1-branch")
        commit("1 commit")
        new_branch("level-2a-branch")
        commit("2a commit")
        check_out("level-1-branch")
        new_branch("level-2b-branch")
        commit("2b commit")
        rewrite_branch_layout_file(
            "root\n"
            "\tlevel-1-branch\n"
            "\t\tlevel-2a-branch\n"
            "\t\tlevel-2b-branch\n")
        check_out("root")
        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_advance"),
            _tool_call(3, "machete_status"),
        )
        assert len(responses) == 4
        for i in (1, 2, 3):
            assert not _result(responses, i)["isError"], i
        assert get_commit_hash("level-1-branch") == get_commit_hash("root")
        assert "level-2a-branch" in _result(responses, 3)["content"][0]["text"]

    def test_session_reapply_status(self, mocker: MockerFixture) -> None:
        """Reapply needs a non-interactive sequence editor (same as test_reapply)."""
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch("level-0-branch")
            commit("Basic commit.")
            new_branch("level-1-branch")
            commit("First level-1 commit.")
            commit("Second level-1 commit.")
            check_out("level-0-branch")
            commit("New commit on level-0-branch")
        rewrite_branch_layout_file(
            "level-0-branch\n\n\tlevel-1-branch\n")
        check_out("level-1-branch")
        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '2s/^pick /fixup /'"):
            with fixed_author_and_committer_date_in_past():
                responses = self._run_session(
                    mocker,
                    _tool_call(1, "machete_status"),
                    _tool_call(2, "machete_reapply"),
                    _tool_call(3, "machete_status"),
                )
        assert len(responses) == 4
        for i in (1, 2, 3):
            assert not _result(responses, i)["isError"], i
        t3 = _result(responses, 3)["content"][0]["text"]
        assert "level-1-branch" in t3

    def test_session_squash_delete_unmanaged_status(self, mocker: MockerFixture) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch("branch-0")
            commit("First commit.")
            commit("Second commit.")
            fork_point = get_current_commit_hash()
            commit("Third commit.")
            commit("Fourth commit.")
        rewrite_branch_layout_file("branch-0\n")

        new_branch("unmanaged")
        commit("unmanaged tip")
        check_out("branch-0")

        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_squash", {"fork_point": fork_point}),
            _tool_call(3, "machete_status"),
            _tool_call(4, "machete_delete_unmanaged"),
            _tool_call(5, "machete_status"),
        )
        assert len(responses) == 6
        assert not _result(responses, 1)["isError"]
        assert not _result(responses, 2)["isError"]
        assert "Squashed" in _result(responses, 2)["content"][0]["text"]
        assert not _result(responses, 3)["isError"]
        assert not _result(responses, 4)["isError"]
        assert "unmanaged" in _result(responses, 4)["content"][0]["text"].lower()
        assert not _result(responses, 5)["isError"]

    def test_session_slide_out_remote_prune_status_file(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()
        new_branch("main")
        commit()
        push()
        check_out("main")
        new_branch("should_be_pruned")
        commit()
        push()
        delete_remote_branch("origin/should_be_pruned")
        check_out("main")
        rewrite_branch_layout_file("main\n\tshould_be_pruned\n")

        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_slide_out", {
                "removed_from_remote": True,
                "delete": True,
            }),
            _tool_call(3, "machete_status"),
            _tool_call(4, "machete_file"),
        )
        assert len(responses) == 5
        assert not _result(responses, 1)["isError"]
        assert not _result(responses, 2)["isError"]
        assert "should_be_pruned" in _result(responses, 2)["content"][0]["text"]
        assert not _result(responses, 3)["isError"]
        assert not _result(responses, 4)["isError"]
        layout = _result(responses, 4)["content"][0]["text"].strip()
        with open(layout, encoding="utf-8") as f:
            assert "should_be_pruned" not in f.read()

    def test_session_invalid_slide_out_then_status(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch("master")
        commit()
        rewrite_branch_layout_file("master\n")
        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_slide_out", {
                "removed_from_remote": True,
                "branches": ["main"],
            }),
            _tool_call(2, "machete_status"),
        )
        assert len(responses) == 3
        assert _result(responses, 1)["isError"]
        assert "removed_from_remote" in _result(responses, 1)["content"][0]["text"]
        assert not _result(responses, 2)["isError"]

    def test_session_github_invalid_subcommand_then_status(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch("master")
        commit()
        rewrite_branch_layout_file("master\n")
        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_github", {"subcommand": "not-a-valid-subcommand"}),
            _tool_call(2, "machete_status"),
        )
        assert len(responses) == 3
        assert _result(responses, 1)["isError"]
        assert "Unknown subcommand" in _result(responses, 1)["content"][0]["text"]
        assert not _result(responses, 2)["isError"]

    def test_session_github_anno_retarget_status(self, mocker: MockerFixture) -> None:
        """PR #15 targets master while machete parent of feature is develop — retarget fixes base."""
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = MockGitHubAPIState.with_prs(
            mock_pr_json(head='feature', base='master', number=15),
        )
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_github_urlopen(github_api_state))

        create_repo_with_remote()
        add_remote('new_origin', 'https://github.com/user/repo.git')
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        commit()
        push()
        new_branch("feature")
        commit()
        push()
        check_out("feature")
        rewrite_branch_layout_file(
            """
            master
                develop
                    feature
            """)

        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_github", {"subcommand": "anno-prs", "with_urls": True}),
            _tool_call(3, "machete_status"),
            _tool_call(4, "machete_github", {"subcommand": "retarget-pr"}),
            _tool_call(5, "machete_status"),
        )
        assert len(responses) == 6
        for i in (1, 2, 3, 4, 5):
            assert not _result(responses, i)["isError"], i
        assert "PR #15" in _result(responses, 3)["content"][0]["text"]
        t4 = _result(responses, 4)["content"][0]["text"].lower()
        assert "develop" in t4
        pr15 = github_api_state.get_pull_by_number(15)
        assert pr15 is not None
        assert pr15["base"]["ref"] == "develop"

    def test_session_github_restack_update_descriptions_status(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')
        github_api_state = _github_api_state_for_restack_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_github_urlopen(github_api_state))

        create_repo_with_remote()
        add_remote('new_origin', 'https://github.com/user/repo.git')
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        commit()
        push()
        new_branch("feature")
        commit()
        push()
        rewrite_branch_layout_file(
            """
            master
                develop
                feature
            """)

        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_github", {"subcommand": "restack-pr"}),
            _tool_call(3, "machete_status"),
            _tool_call(4, "machete_github", {
                "subcommand": "update-pr-descriptions",
                "all": True,
            }),
            _tool_call(5, "machete_status"),
        )
        assert len(responses) == 6
        for i in (1, 2, 3, 4, 5):
            assert not _result(responses, i)["isError"], i
        t2 = _result(responses, 2)["content"][0]["text"]
        assert "PR #15" in t2
        assert "master" in t2.lower()
        pr = github_api_state.get_pull_by_number(15)
        assert pr is not None
        assert pr["base"]["ref"] == "master"
        t4 = _result(responses, 4)["content"][0]["text"]
        assert "description" in t4.lower()

    def test_session_github_create_pr_checkout_prs_status(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        github_api_state = MockGitHubAPIState.with_prs()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_github_urlopen(github_api_state))

        create_repo_with_remote()
        new_branch("main")
        commit()
        push()
        new_branch("develop")
        commit()
        push()
        new_branch("feature")
        commit()
        push()
        rewrite_branch_layout_file("main\ndevelop\n\tfeature")
        check_out("feature")

        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_github", {
                "subcommand": "create-pr",
                "base": "main",
            }),
            _tool_call(3, "machete_status"),
            _tool_call(4, "machete_github", {
                "subcommand": "checkout-prs",
                "request_ids": [1],
            }),
            _tool_call(5, "machete_status"),
        )
        assert len(responses) == 6
        for i in (1, 2, 3, 4, 5):
            assert not _result(responses, i)["isError"], i
        pr = github_api_state.get_pull_by_number(1)
        assert pr is not None
        assert pr["base"]["ref"] == "main"
        assert pr["head"]["ref"] == "feature"
        assert "PR #1" in _result(responses, 3)["content"][0]["text"]

    def test_session_github_checkout_prs_mine_status(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        github_api_state = MockGitHubAPIState.with_prs(
            mock_pr_json(head='develop', base='master', number=1, user='github_user'),
        )
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_github_urlopen(github_api_state))

        create_repo_with_remote()
        add_remote('new_origin', 'https://github.com/user/repo.git')
        new_branch("master")
        commit()
        push()
        new_branch("develop")
        commit()
        push()
        delete_remote_branch("origin/develop")
        check_out("master")
        rewrite_branch_layout_file("master\n")

        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_github", {"subcommand": "checkout-prs", "mine": True}),
            _tool_call(3, "machete_status"),
        )
        assert len(responses) == 4
        for i in (1, 2, 3):
            assert not _result(responses, i)["isError"], i
        assert "develop" in _result(responses, 3)["content"][0]["text"].lower()

    def test_session_gitlab_anno_mrs_then_status(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        gitlab_api_state = MockGitLabAPIState.with_mrs(
            mock_mr_json(head='develop', base='master', number=3, user='gitlab_user'),
        )
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_gitlab_urlopen(gitlab_api_state))

        create_repo_with_remote()
        add_remote('new_origin', 'https://gitlab.com/user/repo.git')
        new_branch("master")
        commit()
        push()
        new_branch("develop")
        commit()
        push()
        check_out("master")
        rewrite_branch_layout_file("master\n\tdevelop\n")

        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_status"),
            _tool_call(2, "machete_gitlab", {"subcommand": "anno-mrs"}),
            _tool_call(3, "machete_status"),
        )
        assert len(responses) == 4
        for i in (1, 2, 3):
            assert not _result(responses, i)["isError"], i
        assert "MR !3" in _result(responses, 3)["content"][0]["text"]

    def test_session_github_anno_prs_no_remotes(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch("master")
        commit()
        rewrite_branch_layout_file("master\n")

        responses = self._run_session(
            mocker,
            _tool_call(1, "machete_github", {"subcommand": "anno-prs", "with_urls": True}),
            _tool_call(2, "machete_status"),
        )
        assert len(responses) == 3
        assert _result(responses, 1)["isError"]
        assert "No remotes defined" in _result(responses, 1)["content"][0]["text"]
        assert not _result(responses, 2)["isError"]
