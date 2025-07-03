import itertools
from typing import List, Optional

from git_machete.annotation import Annotation, Qualifiers
from git_machete.client.base import (PickRoot, SquashMergeDetection,
                                     TraverseReturnTo, TraverseStartFrom)
from git_machete.client.with_code_hosting import MacheteClientWithCodeHosting
from git_machete.code_hosting import PullRequest
from git_machete.exceptions import (InteractionStopped, MacheteException,
                                    UnexpectedMacheteException)
from git_machete.git_operations import LocalBranchShortName, SyncToRemoteStatus
from git_machete.utils import (bold, flat_map, fmt, get_pretty_choices,
                               get_right_arrow)


class TraverseMacheteClient(MacheteClientWithCodeHosting):
    def traverse(
            self,
            *,
            opt_fetch: bool,
            opt_list_commits: bool,
            opt_merge: bool,
            opt_no_edit_merge: bool,
            opt_no_interactive_rebase: bool,
            opt_push_tracked: bool,
            opt_push_untracked: bool,
            opt_return_to: TraverseReturnTo,
            opt_squash_merge_detection: SquashMergeDetection,
            opt_start_from: TraverseStartFrom,
            opt_sync_github_prs: bool,
            opt_sync_gitlab_mrs: bool,
            opt_yes: bool
    ) -> None:
        self._git.expect_no_operation_in_progress()
        self.expect_at_least_one_managed_branch()

        self._set_empty_line_status()
        any_action_suggested: bool = False

        if opt_fetch:
            for rem in self._git.get_remotes():
                if self.remote_enabled_for_traverse_fetch(rem):
                    print(f"Fetching {bold(rem)}...")
                    self._git.fetch_remote(rem)
            if self._git.get_remotes():
                print("")

        current_user: Optional[str] = None
        if opt_sync_github_prs or opt_sync_gitlab_mrs:
            self._init_code_hosting_client()
            current_user = self.code_hosting_client.get_current_user_login()

        initial_branch = nearest_remaining_branch = self._git.get_current_branch()

        if opt_start_from == TraverseStartFrom.ROOT:
            dest = self.root_branch_for(self._git.get_current_branch(), if_unmanaged=PickRoot.FIRST)
            self._print_new_line(False)
            print(f"Checking out the root branch ({bold(dest)})")
            self._git.checkout(dest)
            current_branch = dest
        elif opt_start_from == TraverseStartFrom.FIRST_ROOT:
            # Note that we already ensured that there is at least one managed branch.
            dest = self.managed_branches[0]
            self._print_new_line(False)
            print(f"Checking out the first root branch ({bold(dest)})")
            self._git.checkout(dest)
            current_branch = dest
        else:  # cli_opts.opt_start_from == TraverseStartFrom.HERE
            current_branch = self._git.get_current_branch()
            self.expect_in_managed_branches(current_branch)

        branch: LocalBranchShortName
        for branch in itertools.dropwhile(lambda x: x != current_branch, self.managed_branches.copy()):
            upstream = self.up_branch_for(branch)

            needs_slide_out: bool = self._is_merged_to_upstream(
                branch, opt_squash_merge_detection=opt_squash_merge_detection)
            if needs_slide_out and branch in self.annotations:
                needs_slide_out = self.annotations[branch].qualifiers.slide_out
            s, remote = self._git.get_combined_remote_sync_status(branch)
            if s in (
                    SyncToRemoteStatus.BEHIND_REMOTE,
                    SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE):
                needs_remote_sync = True
            elif s in (
                    SyncToRemoteStatus.UNTRACKED,
                    SyncToRemoteStatus.AHEAD_OF_REMOTE,
                    SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE):
                needs_remote_sync = True
                if branch in self.annotations:
                    needs_remote_sync = self.annotations[branch].qualifiers.push
                if not opt_push_tracked and not opt_push_untracked:
                    needs_remote_sync = False
            else:
                needs_remote_sync = False

            needs_retarget_pr = False
            if opt_sync_github_prs or opt_sync_gitlab_mrs:
                prs = list(filter(lambda pr: pr.head == branch, self._get_all_open_prs()))
                if len(prs) > 1:
                    spec = self.code_hosting_spec
                    raise MacheteException(
                        f"Multiple {spec.pr_short_name}s have <b>{branch}</b> as its {spec.head_branch_name} branch: " +
                        ", ".join(_pr.short_display_text() for _pr in prs))
                pr = prs[0] if prs else None
                needs_retarget_pr = pr is not None and upstream is not None and pr.base != upstream

            needs_create_pr = False
            if opt_sync_github_prs or opt_sync_gitlab_mrs:
                if upstream:
                    prs = [_pr for _pr in self._get_all_open_prs() if _pr.head == branch]
                    if not prs:
                        needs_create_pr = True

            use_merge = opt_merge or (branch in self.annotations and self.annotations[branch].qualifiers.update_with_merge)

            if needs_slide_out:
                # Avoid unnecessary fork point check if we already know that the
                # branch qualifies for slide out;
                # neither rebase nor merge will be suggested in such case anyway.
                needs_parent_sync: bool = False
            elif s == SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                # Avoid unnecessary fork point check if we already know that the
                # branch qualifies for resetting to remote counterpart;
                # neither rebase nor merge will be suggested in such case anyway.
                needs_parent_sync = False
            elif use_merge:
                needs_parent_sync = bool(
                    upstream and not self._git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()))
            else:  # using rebase
                needs_parent_sync = bool(
                    upstream and
                    not (self._git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()) and
                         (self._git.get_commit_hash_by_revision(upstream) ==
                          self.fork_point(branch, use_overrides=True)))
                )
                if needs_parent_sync and branch in self.annotations:
                    needs_parent_sync = self.annotations[branch].qualifiers.rebase

            needs_any_action = needs_slide_out or needs_parent_sync or needs_remote_sync or needs_retarget_pr or needs_create_pr
            if branch != current_branch and needs_any_action:
                self._print_new_line(False)
                print(f"Checking out {bold(branch)}")
                self._git.checkout(branch)
                current_branch = branch
                self._print_new_line(False)
                self.status(
                    warn_when_branch_in_sync_but_fork_point_off=True,
                    opt_list_commits=opt_list_commits,
                    opt_list_commits_with_hashes=False,
                    opt_squash_merge_detection=opt_squash_merge_detection)
                self._print_new_line(True)
            if needs_slide_out:
                any_action_suggested = True
                self._print_new_line(False)
                assert upstream is not None
                ans: str = self.ask_if(f"Branch {bold(branch)} is merged into {bold(upstream)}. "
                                       f"Slide {bold(branch)} out of the tree of branch dependencies?" +
                                       get_pretty_choices('y', 'N', 'q', 'yq'),
                                       f"Branch {bold(branch)} is merged into {bold(upstream)}. "
                                       f"Sliding {bold(branch)} out of the tree of branch dependencies...",
                                       opt_yes=opt_yes)
                if ans in ('y', 'yes', 'yq'):
                    dbb = self.down_branches_for(branch) or []
                    if nearest_remaining_branch == branch:
                        if dbb:
                            nearest_remaining_branch = dbb[0]
                        else:
                            nearest_remaining_branch = upstream
                    for down_branch in dbb:
                        self._state.up_branch_for[down_branch] = upstream
                    self._state.down_branches_for[upstream] = flat_map(
                        lambda ud: dbb if ud == branch else [ud],
                        self._state.down_branches_for[upstream] or [])
                    if branch in self._state.annotations:
                        del self._state.annotations[branch]
                    self.save_branch_layout_file()
                    self._run_post_slide_out_hook(new_upstream=upstream, slid_out_branch=branch, new_downstreams=dbb)
                    if ans == 'yq':
                        return
                    else:
                        # No need to sync branch 'branch' with remote since it just got removed from the tree of dependencies.
                        continue  # pragma: no cover; this line is actually covered, it just doesn't show up due to bug in coverage tooling
                elif ans in ('q', 'quit'):
                    return
                # If user answered 'no', we don't try to rebase/merge but still
                # suggest to sync with remote (if needed; very rare in practice).
            elif needs_parent_sync:
                any_action_suggested = True
                self._print_new_line(False)
                assert upstream is not None
                if use_merge:
                    ans = self.ask_if(f"Merge {bold(upstream)} into {bold(branch)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Merging {bold(upstream)} into {bold(branch)}...", opt_yes=opt_yes)
                else:
                    ans = self.ask_if(f"Rebase {bold(branch)} onto {bold(upstream)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Rebasing {bold(branch)} onto {bold(upstream)}...", opt_yes=opt_yes)
                if ans in ('y', 'yes', 'yq'):
                    if use_merge:
                        self._git.merge(branch=upstream, into=branch, opt_no_edit_merge=opt_no_edit_merge)
                        # It's clearly possible that merge can be in progress
                        # after 'git merge' returned non-zero exit code;
                        # this happens most commonly in case of conflicts.
                        # As for now, we're not aware of any case when merge can
                        # be still in progress after 'git merge' returns zero,
                        # at least not with the options that git-machete passes
                        # to merge; this happens though in case of 'git merge
                        # --no-commit' (which we don't ever invoke).
                        # It's still better, however, to be on the safe side.
                        if self._git.is_merge_in_progress():
                            print("\nMerge in progress; stopping the traversal")
                            return
                    else:
                        fork_point = self.fork_point(branch, use_overrides=True)

                        self.rebase(
                            onto=LocalBranchShortName.of(upstream).full_name(),
                            from_exclusive=fork_point,
                            branch=branch,
                            opt_no_interactive_rebase=opt_no_interactive_rebase)
                        # It's clearly possible that rebase can be in progress after 'git rebase' returned non-zero exit code;
                        # this happens most commonly in case of conflicts, regardless of whether the rebase is interactive or not.
                        # But for interactive rebases, it's still possible that even if 'git rebase' returned zero, the rebase is still
                        # in progress; e.g. when interactive rebase gets to 'edit' command, it will exit returning zero, but the rebase
                        # will be still in progress, waiting for user edits and a subsequent 'git rebase --continue'.
                        rebased_branch = self._git.get_currently_rebased_branch_or_none()
                        if rebased_branch:  # 'rebased_branch' should be equal to 'branch' at this point anyway
                            print(fmt(f"\nRebase of {bold(rebased_branch)} in progress; stopping the traversal"))
                            return
                    if ans == 'yq':
                        return

                    s, remote = self._git.get_combined_remote_sync_status(branch)
                    if s in (
                            SyncToRemoteStatus.BEHIND_REMOTE,
                            SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE):
                        # This case is extremely unlikely in practice.
                        #
                        # For a freshly rebased/merged branch to be behind its remote, would require a specially crafted scenario
                        # (so that author/commit dates in the resulting rebased/merge commit align perfectly
                        # with the commits already present in remote).
                        #
                        # For a freshly rebased/merged branch to be diverged from and older than remote,
                        # would require a divergence in clocks between local and remote (so that the "physically older" commit in remote
                        # is still considered "logically newer" than the "physically newer" rebased/merge commit).
                        needs_remote_sync = True
                    elif s in (
                            SyncToRemoteStatus.UNTRACKED,
                            SyncToRemoteStatus.AHEAD_OF_REMOTE,
                            SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE):
                        needs_remote_sync = True
                        if branch in self.annotations:
                            needs_remote_sync = self.annotations[branch].qualifiers.push
                    else:
                        needs_remote_sync = False

                elif ans in ('q', 'quit'):
                    return

            if needs_retarget_pr:
                any_action_suggested = True
                assert pr is not None
                assert upstream is not None
                spec = self.code_hosting_spec
                self._print_new_line(False)
                ans_intro = f"Branch {bold(branch)} has a different {spec.pr_short_name} {spec.base_branch_name} ({bold(pr.base)}) " \
                    f"in {spec.display_name} than in machete file ({bold(upstream)}).\n"
                ans = self.ask_if(
                    ans_intro + f"Retarget {pr.display_text()} to {bold(upstream)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
                    ans_intro + f"Retargeting {pr.display_text()} to {bold(upstream)}...",
                    opt_yes=opt_yes)
                if ans in ('y', 'yes', 'yq'):
                    self.code_hosting_client.set_base_of_pull_request(pr.number, base=upstream)
                    print(f'{spec.base_branch_name.capitalize()} branch of {pr.display_text()} has been switched to {bold(upstream)}')
                    pr.base = upstream

                    anno = self._state.annotations.get(branch)
                    self._state.annotations[branch] = Annotation(self._pull_request_annotation(pr, current_user),
                                                                 anno.qualifiers if anno else Qualifiers())
                    self.save_branch_layout_file()

                    new_description = self._get_updated_pull_request_description(pr)
                    if pr.description != new_description:
                        self.code_hosting_client.set_description_of_pull_request(pr.number, description=new_description)
                        print(f'Description of {pr.display_text()} has been updated')
                        pr.description = new_description

                    applicable_prs: List[PullRequest] = self._get_applicable_pull_requests(related_to=pr)
                    for pr in applicable_prs:
                        new_description = self._get_updated_pull_request_description(pr)
                        if pr.description != new_description:
                            self.code_hosting_client.set_description_of_pull_request(pr.number, description=new_description)
                            pr.description = new_description
                            print(fmt(f'Description of {pr.display_text()} '
                                      f'(<b>{pr.head} {get_right_arrow()} {pr.base}</b>) has been updated'))

                    if ans == 'yq':
                        return
                elif ans in ('q', 'quit'):
                    return

            if needs_remote_sync:
                any_action_suggested = True
                try:
                    if s == SyncToRemoteStatus.BEHIND_REMOTE:
                        assert remote is not None
                        self._handle_behind_state(branch=current_branch, remote=remote, opt_yes=opt_yes)
                    elif s == SyncToRemoteStatus.AHEAD_OF_REMOTE:
                        assert remote is not None
                        self._handle_ahead_state(
                            current_branch=current_branch,
                            remote=remote,
                            is_called_from_traverse=True,
                            opt_push_tracked=opt_push_tracked,
                            opt_yes=opt_yes)
                    elif s == SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                        self._handle_diverged_and_older_state(current_branch, opt_yes=opt_yes)
                    elif s == SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                        assert remote is not None
                        self._handle_diverged_and_newer_state(
                            current_branch=current_branch,
                            remote=remote,
                            opt_push_tracked=opt_push_tracked,
                            opt_yes=opt_yes)
                    elif s == SyncToRemoteStatus.UNTRACKED:
                        self._handle_untracked_state(
                            branch=current_branch,
                            is_called_from_traverse=True,
                            is_called_from_code_hosting=False,
                            opt_push_untracked=opt_push_untracked,
                            opt_push_tracked=opt_push_tracked,
                            opt_yes=opt_yes)
                    else:
                        raise UnexpectedMacheteException(f"Unexpected SyncToRemoteStatus: {s}.")
                except InteractionStopped:
                    return

            if needs_create_pr:
                any_action_suggested = True
                assert upstream is not None
                spec = self.code_hosting_spec
                self._print_new_line(False)
                ans_intro = f"Branch {bold(branch)} does not have {spec.pr_short_name_article} {spec.pr_short_name}" \
                    f" in {spec.display_name}.\n"
                ans = self.ask_if(
                    ans_intro + f"Create {spec.pr_short_name_article} {spec.pr_short_name} "
                    f"from {bold(branch)} to {bold(upstream)}?" + get_pretty_choices('y', 'd[raft]', 'N', 'q', 'yq'),
                    ans_intro + f"Creating {spec.pr_short_name_article} {spec.pr_short_name} "
                    f"from {bold(branch)} to {bold(upstream)}...",
                    opt_yes=opt_yes)
                if ans in ('y', 'yes', 'yq', 'd', 'draft'):
                    self.create_pull_request(
                        head=current_branch,
                        opt_draft=(ans in ('d', 'draft')),
                        opt_title=None,
                        opt_update_related_descriptions=True,
                        opt_yes=opt_yes)
                    if ans == 'yq':
                        return
                elif ans in ('q', 'quit'):
                    return

        if opt_return_to == TraverseReturnTo.HERE:
            self._git.checkout(initial_branch)
        elif opt_return_to == TraverseReturnTo.NEAREST_REMAINING:
            self._git.checkout(nearest_remaining_branch)
        # otherwise opt_return_to == TraverseReturnTo.STAY, so no action is needed

        self._print_new_line(False)
        self.status(
            warn_when_branch_in_sync_but_fork_point_off=True,
            opt_list_commits=opt_list_commits,
            opt_list_commits_with_hashes=False,
            opt_squash_merge_detection=opt_squash_merge_detection)
        print("")
        if current_branch == self.managed_branches[-1]:
            msg: str = f"Reached branch {bold(current_branch)} which has no successor"
        else:
            msg = f"No successor of {bold(current_branch)} needs to be slid out or synced with upstream branch or remote"
        print(f"{msg}; nothing left to update")
        if not any_action_suggested and initial_branch not in self._state.roots:
            print(fmt("Tip: `traverse` by default starts from the current branch, "
                      "use flags (`--start-from=`, `--whole` or `-w`, `-W`) to change this behavior.\n"
                      "Further info under `git machete traverse --help`."))
        if opt_return_to == TraverseReturnTo.HERE or (
                opt_return_to == TraverseReturnTo.NEAREST_REMAINING and nearest_remaining_branch == initial_branch):
            print(f"Returned to the initial branch {bold(initial_branch)}")
        elif opt_return_to == TraverseReturnTo.NEAREST_REMAINING and nearest_remaining_branch != initial_branch:
            print(
                f"The initial branch {bold(initial_branch)} has been slid out. "
                f"Returned to nearest remaining managed branch {bold(nearest_remaining_branch)}")
