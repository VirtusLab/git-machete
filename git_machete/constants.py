from enum import Enum, IntEnum

from git_machete.exceptions import MacheteException

MAX_COUNT_FOR_INITIAL_LOG = 10
DISCOVER_DEFAULT_FRESH_BRANCH_COUNT = 10
MAX_COMMITS_FOR_SQUASH_MERGE_DETECTION = 1000

PICK_FIRST_ROOT: int = 0
PICK_LAST_ROOT: int = -1


class SyncToRemoteStatuses(IntEnum):
    NO_REMOTES = 0
    UNTRACKED = 1
    IN_SYNC_WITH_REMOTE = 2
    BEHIND_REMOTE = 3
    AHEAD_OF_REMOTE = 4
    DIVERGED_FROM_AND_OLDER_THAN_REMOTE = 5
    DIVERGED_FROM_AND_NEWER_THAN_REMOTE = 6


class GitFormatPatterns(Enum):
    # %ai for ISO-8601 format
    AUTHOR_DATE = "%ai"
    # %aE/%aN (rather than %ae/%an) for respecting .mailmap; see `git rev-list --help`
    AUTHOR_EMAIL = "%aE"
    AUTHOR_NAME = "%aN"
    # subject and body
    FULL_MESSAGE = "%B"
    # subject NOT included
    MESSAGE_BODY = "%b"


class SquashMergeDetection(Enum):
    NONE = "none"
    SIMPLE = "simple"
    EXACT = "exact"

    @staticmethod
    def from_string(value: str, from_where: str) -> 'SquashMergeDetection':
        if value == "none":
            return SquashMergeDetection.NONE
        if value == "simple":
            return SquashMergeDetection.SIMPLE
        if value == "exact":
            return SquashMergeDetection.EXACT
        valid_values = ', '.join(e.value for e in SquashMergeDetection)
        raise MacheteException(f"Invalid value for {from_where}: `{value}`. Valid values are `{valid_values}`")
