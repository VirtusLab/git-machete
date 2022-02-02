from enum import IntEnum, Enum
import os

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


class GitFormatPatterns(Enum):
    AUTHOR_NAME = "%aN"
    AUTHOR_EMAIL = "%aE"
    AUTHOR_DATE = "%ai"
    RAW_BODY = "%B"
    SUBJECT = "%s"
