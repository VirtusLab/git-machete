Select the style of the generated section ("intro") added to the PR description:
  * ``full``                --- include both a chain of upstream PRs (typically leading to ``main``, ``master``, ``develop`` etc.) and a tree of downstream PRs
  * ``full-no-branches``    --- same as ``full``, but no branch names are included (only PR numbers & titles)
  * ``up-only``             --- default, include only a chain of upstream PRs
  * ``up-only-no-branches`` --- same as ``up-only``, but no branch names are included (only PR numbers & titles)
  * ``none``                --- prepend no intro to the PR description at all
