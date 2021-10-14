from enum import IntEnum
import os
from typing import NewType, Union

MAX_COUNT_FOR_INITIAL_LOG = 10
DISCOVER_DEFAULT_FRESH_BRANCH_COUNT = 10

PICK_FIRST_ROOT: int = 0
PICK_LAST_ROOT: int = -1


class EscapeCodes:
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    # `GIT_MACHETE_DIM_AS_GRAY` remains undocumented as for now,
    # was just needed for animated gifs to render correctly (`[2m`-style dimmed text was invisible)
    DIM = '\033[38;2;128;128;128m' if os.environ.get(
        'GIT_MACHETE_DIM_AS_GRAY') == 'true' else '\033[2m'
    UNDERLINE = '\033[4m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    ORANGE = '\033[00;38;5;208m'
    RED = '\033[91m'


class SyncToRemoteStatuses(IntEnum):
    NO_REMOTES = 0
    UNTRACKED = 1
    IN_SYNC_WITH_REMOTE = 2
    BEHIND_REMOTE = 3
    AHEAD_OF_REMOTE = 4
    DIVERGED_FROM_AND_OLDER_THAN_REMOTE = 5
    DIVERGED_FROM_AND_NEWER_THAN_REMOTE = 6


GIT_FORMAT_PATTERNS = {
    "author name": "%aN",
    "author email": "%aE",
    "author date": "%ai",
    "raw body": "%B",
    "subject": "%s"
}
any_branch_type = NewType("any_branch_type", str)
local_branch_type = NewType("local_branch_type", any_branch_type)
remote_branch_type = NewType("remote_branch_type", any_branch_type)
commit_type = NewType("commit_type", str)


class AnyBranch(object):
    pass


class LocalBranch(AnyBranch):
    pass


class RemoteBranch(AnyBranch):
    pass


class Commit(str):
    pass

any_branch: AnyBranch = AnyBranch('A')
local: LocalBranch = LocalBranch("B")
remote: RemoteBranch = RemoteBranch("C")
var: str = "D"

# any_branch = local
# any_branch = remote
# any_branch = var   # fail
# local = any_branch # fail
# remote = any_branch # fail
# var = any_branch
# var = local
# var = remote
# local = remote  #fail
