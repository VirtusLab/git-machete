STATUS_EXTRA_SPACE_BEFORE_BRANCH_NAME = 'machete.status.extraSpaceBeforeBranchName'
TRAVERSE_PUSH = 'machete.traverse.push'
WORKTREE_USE_TOP_LEVEL_MACHETE_FILE = 'machete.worktree.useTopLevelMacheteFile'


def annotate_with_urls(subsection: str) -> str:
    return f'machete.{subsection}.annotateWithUrls'


def force_description_from_commit_message(subsection: str) -> str:
    return f'machete.{subsection}.forceDescriptionFromCommitMessage'


def domain(subsection: str) -> str:
    return f'machete.{subsection}.domain'


def remote(subsection: str) -> str:
    return f'machete.{subsection}.remote'


def organization(subsection: str) -> str:
    return f'machete.{subsection}.organization'


def repository(subsection: str) -> str:
    return f'machete.{subsection}.repository'


def override_fork_point_to(branch: str) -> str:
    return f'machete.overrideForkPoint.{branch}.to'


def override_fork_point_while_descendant_of(branch: str) -> str:
    return f'machete.overrideForkPoint.{branch}.whileDescendantOf'
