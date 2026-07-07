Setting this config key to ``true`` will cause all commands that write GitLab MR numbers into annotations
to not only include MR number and author (if different from the current user), but also the full URL of the MR.

The affected (sub)commands clearly include ``anno --sync-gitlab-mrs`` and ``gitlab anno-mrs``,
but also ``gitlab checkout-mrs``, ``gitlab create-mr``, ``gitlab retarget-mr`` and ``gitlab restack-mr``.
