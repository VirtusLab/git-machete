GITHUB_DOMAIN = 'machete.github.domain'
GITHUB_REMOTE = 'machete.github.remote'
GITHUB_ORGANIZATION = 'machete.github.organization'
GITHUB_REPOSITORY = 'machete.github.repository'
TRAVERSE_PUSH = 'machete.traverse.push'
WORKTREE_USE_TOP_LEVEL_MACHETE_FILE = 'machete.worktree.useTopLevelMacheteFile'
STATUS_EXTRA_SPACE_BEFORE_BRANCH_NAME = 'machete.status.extraSpaceBeforeBranchName'


def override_fork_point_to(branch: str) -> str:
    return f'machete.overrideForkPoint.{branch}.to'


def override_fork_point_while_descendant_of(branch: str) -> str:
    return f'machete.overrideForkPoint.{branch}.whileDescendantOf'
