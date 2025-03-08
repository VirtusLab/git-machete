Select the style of the generated section ("intro") added to the MR description:
  * ``full``                --- include both a chain of upstream MRs (typically leading to ``main``, ``master``, ``develop`` etc.) and a tree of downstream MRs
  * ``full-no-branches``    --- same as ``full``, but no branch names are included (only MR numbers & titles)
  * ``up-only``             --- default, include only a chain of upstream MRs
  * ``up-only-no-branches`` --- same as ``up-only``, but no branch names are included (only MR numbers & titles)
  * ``none``                --- prepend no intro to the MR description at all
