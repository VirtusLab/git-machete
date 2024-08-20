from enum import Enum
from typing import Optional

from git_machete.exceptions import MacheteException

DISCOVER_DEFAULT_FRESH_BRANCH_COUNT = 10
MAX_COMMITS_FOR_SQUASH_MERGE_DETECTION = 1000
INITIAL_COMMIT_COUNT_FOR_LOG = 10
TOTAL_COMMIT_COUNT_FOR_LOG = 100


class SquashMergeDetection(Enum):
    NONE = "none"
    SIMPLE = "simple"
    EXACT = "exact"

    @staticmethod
    def from_string(value: str, from_where: Optional[str]) -> 'SquashMergeDetection':
        try:
            return SquashMergeDetection[value.upper()]
        except KeyError:
            valid_values = ', '.join(e.value for e in SquashMergeDetection)
            prefix = f"Invalid value for {from_where}" if from_where else "Invalid value"
            raise MacheteException(f"{prefix}: `{value}`. Valid values are `{valid_values}`")
