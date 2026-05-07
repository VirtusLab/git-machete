"""Date helpers.

Kept as a separate (one-function) module so that tests can patch
`git_machete.utils.date.get_current_date` cleanly without coupling the
date logic to file-system or markup concerns.
"""

import datetime


def get_current_date() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")
