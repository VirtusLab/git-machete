Controls the warning shown when creating a pull/merge request whose base and head branches live in different repositories.
Set to ``false`` to suppress the warning about creating stacked pull/merge requests from forks; enabled by default.
This setting affects only the warning, not repository selection or request creation.
For example, run ``git config advice.macheteCreateFromFork false`` in a repository, or add ``--global`` to apply it everywhere.
