Setting this config key to ``true`` will cause all commands that write GitHub PR numbers into annotations
to not only include PR number and author (if different from the current user), but also the full URL of the PR.

The affected (sub)commands clearly include ``anno --sync-github-prs`` and ``github anno-prs``,
but also ``github checkout-prs``, ``github create-pr``, ``github retarget-pr`` and ``github restack-pr``.
