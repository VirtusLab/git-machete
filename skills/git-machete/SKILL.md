---
name: git-machete
description: Use whenever invoking the `git machete` CLI to organize branch chains, compute fork points, run stacked rebases/merges, or manage GitHub/GitLab PR/MR chains - especially in a repo that already has a `.git/machete` file. Lists which subcommands modify `.git/machete`, run rebase/merge, run hooks, or read stdin, so the agent can pick the right one and pass the right flags. Crucially, names the commands that MUST be invoked with `-y/--yes` (and the few that have no `-y` and therefore must NOT be invoked at all without a tty) so the agent never hangs on an interactive prompt. Also warns against hand-editing the `.git/machete` layout file.
---

# git-machete

`git machete` is a logic- and feature-heavy CLI for managing chains of branches, but it keeps almost no extra state of its own: the only user-visible file it owns is `.git/machete` (the "branch layout" - a tree of branches with parent/child relationships, fork points and PR/MR annotations). It also maintains a transparent merge-base cache for performance, which the user never needs to touch. Everything else - rebases, merges, pushes, status rendering, PR/MR creation - is driven straight off git and the hosting API.

If the repo has no `.git/machete` file yet (check with `git machete file && test -s "$(git machete file)"`), the layout has not been initialized: run `git machete discover -y` (or ask the user) before anything else.

**Do not run `git machete discover` against an already-initialized layout** unless the user explicitly asks for it. `discover` re-derives the entire layout from heuristics (recent commit dates, branch reachability) and silently overwrites any hand-curated ordering, parenting, or annotations the user has built up. Use the targeted commands (`add`, `slide-out`, hand-edit) for incremental changes.

## Hard rules - read first

1. **Prefer dedicated subcommands over hand-editing `.git/machete`** when one fits the task. You *can* edit the layout file directly, but parse errors are quiet, so reach for a subcommand whenever there is one that fits:
   - `git machete add [-y] [<branch>] [--as-root|--onto <parent>]` - add a branch
   - `git machete slide-out [<branch>...]` - remove a branch and re-parent its children (non-interactive by default; see rule 4 for `--delete`)
   - `git machete anno [<text>]` - set/clear annotation on the current branch
   - `git machete rename <new-name>` - rename a local branch *and* its layout entry (use this instead of `git branch -m`)

   The layout file grammar is small: one branch per line, each child indented one level deeper than its parent, with an optional annotation after whitespace on the same line. Any consistent indent unit works (a tab or N spaces), but the same unit must be used throughout the file.

   For operations with no dedicated command (e.g. reparenting an existing branch, splitting one branch into two, ad-hoc reordering of siblings), hand-edit `.git/machete` directly. The file is small and brittle: edit it in place with the agent's structured editing tool (`StrReplace` / equivalent string-replacement primitive), not by piping it through `sed`/`awk` or rewriting it from a shell heredoc - one stray space changes the parent/child relationship silently. Recommended sequence:

   1. `MACHETE="$(git machete file)"` - resolve the actual path (worktree/submodule-aware).
   2. `cp -a "$MACHETE" "$MACHETE~"` - back up; the file is NOT tracked by git, so this is your only undo.
   3. Read the file, perform a structured in-place edit (preserve the existing indent unit), write it back.
   4. `git machete status` - verify the parse. If it errors, restore with `cp -a "$MACHETE~" "$MACHETE"`.

   When indenting, match the unit already used in the file (could be a tab or any number of spaces, but it must stay consistent throughout). For a brand-new layout, use two spaces.

   In the common case the layout file lives at `.git/machete` and hard-coding that is fine. The two exceptions are submodules (`.git/modules/<path>/machete`) and linked worktrees with `git config machete.worktree.useTopLevelMacheteFile false` (`.git/worktrees/<wt-name>/machete`); when in doubt, `git machete file` always resolves correctly.

2. **Register every new branch in the layout.** Whenever you create a branch as part of the user's actual work (`git checkout -b ...`, `git switch -c ...`, `git branch ...`), follow it with `git machete add -y [--onto <parent>]` so the new branch joins `.git/machete`.
   In a git-machete-managed repo, the layout is the index of "branches I care about": users typically keep every branch they actively touch under git-machete, and the only branches deliberately left out are unrelated ones (someone else's WIP, throwaway branches checked out for a quick look).
   Defer to the user if they ask you to leave a branch unmanaged - but don't *silently* skip the `add` step; ask if you're unsure.

3. **Never invoke a command that reads stdin without `-y/--yes`.** Commands with a `-y/--yes` flag: `add`, `advance`, `clean`, `delete-unmanaged`, `discover`, `traverse`, `github create-pr`, `gitlab create-mr`. Always pass `-y` from a non-interactive context (CI, agent, script).

4. **Some commands prompt and have no `-y` to suppress it - avoid or work around them**:
   - `git machete update` - prompts only if the current branch is missing from the layout. **Workaround**: `git machete add -y` first, then `git machete update`.
   - `git machete status` - prompts to slide out stale branches when stdout is a tty. **Workaround**: pipe through `| cat` or redirect, or use `git machete status --color=never > /tmp/status.txt`.
   - `git machete slide-out --delete ...` - prompts once per branch and the prompt can't be silenced. **Workaround**: run plain `git machete slide-out <branch>...` first, then `git branch -D <branch>...` yourself (or skip the `--delete` entirely). Plain `slide-out` (and `slide-out --removed-from-remote`) is non-interactive.
   - `git machete go` *without* a direction - opens an interactive single-keystroke picker. **Never invoke this form from an agent.** Use `git machete go <direction>` (`up`/`down`/`prev`/`next`/`root`/`first`/`last`) instead, which is non-interactive (but may still prompt if `down` is ambiguous - prefer `git machete show down | head -1` for scripted child discovery).
   - `git machete edit` - opens `$EDITOR`. **Never invoke this form from an agent.** Use the dedicated subcommands from rule 1, or hand-edit `.git/machete` for the cases that have no subcommand.

5. **Plumbing commands have stable output across minor versions** and are safe for scripting. Use these for any "I need to read state from git-machete" task:
   - `git machete file` - absolute path of `.git/machete`
   - `git machete fork-point [--inferred] [<branch>]` - prints fork-point SHA on stdout (and only that)
   - `git machete is-managed [<branch>]` - exit code 0 if managed, non-zero otherwise; **no stdout**
   - `git machete list <category> [<branch>]` - newline-separated branch names; categories: `managed`, `addable`, `childless`, `slidable`, `slidable-after <branch>`, `unmanaged`, `with-overridden-fork-point`
   - `git machete show <direction> [<branch>]` - newline-separated branch names for the given direction
   - `git machete version` - prints `git-machete version X.Y.Z`

   All other commands' stdout/stderr formatting may change between minor versions, including `status`.

6. **Resolve yellow edges before running `update`/`traverse`.** A yellow edge means a child branch is a descendant of its parent *but* git-machete's inferred fork point lies somewhere earlier than the parent tip - usually because the branch was rebased over commits from another branch, or its real parent is a different managed branch. In ASCII-only output the edge marker is `?-` (e.g. `?-feature-x`); with colour it's yellow. **Do not run `git machete update` / `git machete traverse` blindly in this state** - a rebase from the inferred fork point will pull extra commits onto the branch.

   Instead, run `git machete status --list-commits --color=never | cat` (which prints the relevant suggestion under the tree) and present the options to the user. The three resolutions, in roughly the order to consider them, are:
   - `git machete fork-point <branch> --override-to-parent` - accept the parent branch tip as the fork point (use when the branch was rebased and the inferred fork point is stale).
   - `git machete update` (rebase) - only after confirming the inferred fork point really is correct and the extra commits should be re-applied.
   - Reattach the branch under a different parent (e.g. hand-edit `.git/machete` as in rule 1) - use when the layout is wrong and the branch's real parent is a different managed branch.

   Pick based on what the user wants; don't auto-choose.

## Command catalog with side effects

The table lists every non-deprecated top-level command and `github`/`gitlab` subcommand. The brace notation `{github,gitlab} verb-{pr,mr}` is shorthand for the pair `github verb-pr` and `gitlab verb-mr`.

Commands absent from every row (`completion`, `diff`, `help`, `log`, plus the plumbing commands listed above, plus `{github,gitlab} update-{pr,mr}-descriptions` which only talks to the hosting API) do not satisfy any of these properties.

| Side effect                                                          | Commands                                                                                                                                                                                                                                                       |
|----------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| reads stdin<sup>[1]</sup>                                            | `add`, `advance`, `clean`, `delete-unmanaged`, `discover`, `{github,gitlab} create-{pr,mr}`, `go`<sup>[2]</sup>, `slide-out`<sup>[3]</sup>, `status`<sup>[4]</sup>, `traverse`, `update`                                                                        |
| displays status (runs `machete-status-branch` hook)                  | `discover`, `{github,gitlab} create-{pr,mr}`, `{github,gitlab} restack-{pr,mr}`, `go`<sup>[2]</sup>, `status`, `traverse`                                                                                                                                       |
| writes `.git/machete` (branch layout)                                | `add`, `advance`, `anno`, `clean`, `discover`, `edit`<sup>[5]</sup>, `{github,gitlab} anno-{pr,mr}s`, `{github,gitlab} checkout-{pr,mr}s`, `{github,gitlab} create-{pr,mr}`, `{github,gitlab} restack-{pr,mr}`, `{github,gitlab} retarget-{pr,mr}`, `rename`, `slide-out`, `traverse` |
| mutates the git repository (refs / index / worktree / config)<sup>[6]</sup> | `add`, `advance`, `clean`, `delete-unmanaged`, `fork-point`<sup>[7]</sup>, `{github,gitlab} checkout-{pr,mr}s`, `{github,gitlab} create-{pr,mr}`, `{github,gitlab} restack-{pr,mr}`, `go`, `reapply`, `rename`, `slide-out`, `squash`, `traverse`, `update`     |
| runs `git merge`                                                     | `advance`<sup>[8]</sup>, `slide-out`, `traverse`, `update`                                                                                                                                                                                                     |
| runs `git rebase` (runs `machete-pre-rebase` hook)                   | `reapply`<sup>[9]</sup>, `slide-out`, `traverse`, `update`                                                                                                                                                                                                     |
| slides out a branch (runs `machete-post-slide-out` hook)             | `advance`, `slide-out`<sup>[10]</sup>, `traverse`                                                                                                                                                                                                              |
| requires no ongoing rebase / merge / cherry-pick / revert / am / bisect | `advance`, `go`, `reapply`, `slide-out`, `squash`, `traverse`, `update`                                                                                                                                                                                       |

### Footnotes

[1]: Commands with a `-y/--yes` flag (`add`, `advance`, `clean`, `delete-unmanaged`, `discover`, `traverse`, `{github,gitlab} create-{pr,mr}`) are safe to run from an agent **as long as `-y` is passed**. Without `-y` they read stdin to confirm decisions. The rest (see [2]-[4]) cannot be silenced and need a workaround.

[2]: `go` without a direction is fully interactive (single-keystroke picker reading stdin). Never run this form from an agent. `go <direction>` (`up`/`down`/`prev`/`next`/`root`/`first`/`last`) is non-interactive, but `down` may prompt if there are multiple children; prefer `git machete show down` to enumerate them and then check out manually with `git checkout`.

[3]: `slide-out` only reads stdin under `--delete` (one yes/no per branch). `slide-out` and `slide-out --removed-from-remote` without `--delete` are non-interactive.

[4]: `status` reads stdin only when stdout is a tty and the layout references branches that no longer exist in the repo. Redirected/non-tty runs (`| cat`, `> file`) skip the prompt entirely. CI runs are safe.

[5]: `edit` doesn't itself write the layout file; it just opens `$GIT_MACHETE_EDITOR`/`$GIT_EDITOR` on it and any change is done by the editor. Never run this form from an agent.

[6]: Pure hosting-API operations don't count here - that's why `{github,gitlab} retarget-{pr,mr}` and `{github,gitlab} update-{pr,mr}-descriptions` are absent.

[7]: `fork-point` mutates `.git/config` only under its override flags (`--override-to=...`, `--override-to-inferred`, `--override-to-parent`, `--unset-override`). The default mode and `--inferred`/`--explain` are read-only.

[8]: `advance` can only run fast-forward merge (`git merge --ff-only`).

[9]: `reapply` can run rebase but can't run merge (merging a branch with its own fork point is a no-op).

[10]: `slide-out --removed-from-remote` removes branches from the layout but does NOT run the `machete-post-slide-out` hook. The regular `slide-out` and the slide-out triggered by `advance`/`traverse` do.

## Recipes

### Initialize the branch layout for a fresh repo
```bash
git machete discover -y
```
Only run this when the layout doesn't exist yet (or the user explicitly asks to re-derive). On an existing layout, `discover` silently replaces any user-curated parenting/ordering.

### Add the current branch under its parent
```bash
git checkout -b feature/new-thing
git machete add -y
```

### Add a branch under an explicit parent
```bash
git machete add -y --onto develop feature/new-thing
```

### Rename a branch (keeping the layout consistent)
```bash
git machete rename feature/new-name
```
**Do not** use `git branch -m`; it leaves the layout out of sync.

### Get current branch state
```bash
git machete status -l                    # human-friendly, with commits
git machete status -l --color=never | cat   # safe for agents (never prompts)
```

### Sync the current branch with its parent
```bash
git machete update --no-interactive-rebase    # rebase-based (default)
```
If `update` complains the current branch isn't in the layout, run `git machete add -y` (or `git machete discover -y`) first.

### Walk the whole chain and bring everything up to date
```bash
git machete traverse -y --no-push                # rebase only, don't push
git machete traverse -y                          # rebase + push (default)
```

**Do not** pass `-M`/`--merge` (to `update`, `traverse`, or `slide-out`). For stacked branches, merge-based sync entangles history quickly and recovery is non-trivial (see the [README FAQ](https://github.com/VirtusLab/git-machete#can-i-use-git-merge-for-syncing-stacked-branches) for rationale). Rebase is the only mode an agent should use. If the user explicitly asks for merge mode, repeat the warning and ask them to confirm.

### Drop a branch from the layout (after merge)
```bash
git machete slide-out <branch>                          # branch still exists locally; non-interactive
git machete slide-out --removed-from-remote             # clean up branches whose remote is gone (non-interactive, no hook)
```
To also delete the branch from git, run `git branch -D <branch>` yourself after `slide-out` - the built-in `--delete` flag prompts per branch and can't be silenced.

### Inspect / set / clear fork-point overrides
```bash
git machete fork-point                       # prints SHA
git machete fork-point --inferred            # what git-machete would infer
git machete fork-point --explain             # human-readable rationale (uses stderr)
git machete fork-point --override-to-parent  # pin fork point to the parent branch tip
git machete fork-point --unset-override
```

### Create / restack / retarget PRs (GitHub)
```bash
git machete github create-pr -y              # safe: -y skips push/sync prompts
git machete github restack-pr                # non-interactive
git machete github retarget-pr               # non-interactive, hosting-API only
git machete github checkout-prs --mine       # non-interactive (forces non-interactive `add`)
```
GitLab equivalents: `gitlab create-mr -y`, `restack-mr`, `retarget-mr`, `checkout-mrs --mine`.

### Discover children/parent for scripting (instead of `go`)
```bash
git machete show up                          # parent
git machete show down                        # all children, one per line
git machete show prev                        # previous in DFS order
git machete show next                        # next in DFS order
git machete show root                        # root of the current chain
git machete list managed                     # everything in the layout
git machete list slidable                    # branches that can be slid out
```

## Hooks

`git machete` invokes three optional hooks if executable scripts of the matching names exist in `.git/hooks/`:

- `machete-pre-rebase <onto> <fork-point> <branch>` - run before each `git rebase` initiated by git-machete (i.e. from `reapply`, `slide-out`, `traverse`, `update`). Non-zero exit aborts the rebase.
- `machete-post-slide-out <new-upstream> <slid-out-branch> [<new-downstream>...]` - run after a successful slide-out triggered by `advance`, `slide-out` (without `--removed-from-remote`), or `traverse`.
- `machete-status-branch <branch>` - run once per branch during status display; its stdout is appended to the branch's line in `status` output.

## Files this tool reads/writes

| Path                                | Purpose                                                                                                                                                                                                                       |
|-------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `.git/machete`                      | branch layout (parent/child tree, annotations, qualifiers). The literal path varies by context (worktree, submodule); always resolve via `git machete file`. Not git-tracked, so back up to `.git/machete~` before manual edits. |
| `.git/machete-merge-base-cache`     | transparent merge-base cache.                                                                                                                                            |
| `.git/config` (`machete.*` keys)    | fork-point overrides set via `fork-point --override-to=...`; also feature toggles like `machete.worktree.useTopLevelMacheteFile`, `machete.traverse.push`, `machete.squashMergeDetection`.                                    |
| `.git/info/description`             | used as PR/MR title default when creating with `github create-pr` / `gitlab create-mr`.                                                                                                                                       |
| `~/.github-token`                   | GitHub API token (alternative: `GITHUB_TOKEN` env var).                                                                                                                                                                       |
| `~/.gitlab-token`                   | GitLab API token (alternative: `GITLAB_TOKEN` env var).                                                                                                                                                                       |

## Further reading

For per-command detail (full flag list, exit codes, examples), run `git machete help <command>` (e.g. `git machete help traverse`). It prints the same content as the readthedocs page for that subcommand, but in a single plain-text response that's cheap to ingest.
