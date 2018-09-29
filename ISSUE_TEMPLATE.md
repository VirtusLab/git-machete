# Reporting issues

## Expected behavior/subcommand output

## Actual behavior/subcommand output

## `git` and `git machete` versions

`git --version`

`git machete --version`

## Additional diagnostics info

Depending on your NDAs/level of confidentiality of the project stored in your repository, you can also include one of the 3 following variants of diagnostics information:

1. Executed git commands

    `git machete --verbose <problematic-subcommand>` (stdout+stderr)

    If it comes to repository-specific data, this will only include names of local branches and their remote counterparts.
    No commit messages, file paths or file contents will be included.

2. Executed git commands, their outputs and other detailed logging information

    `git machete --debug <problematic-subcommand>` (stdout+stderr)

    If it comes to repository-specific data, this will include names of local branches and their remote counterparts, their full logs (but only wrt. commit hashes) and their full reflogs (which typically include commit messages).
    No file paths or file contents will be included.

3. Executed git commands, their outputs and other detailed logging information, and `.git` folder

    `git machete --debug <problematic-subcommand>` (stdout+stderr)

    AND

    `tar czvf dotgit.tgz .git/`

    Sharing contents of `.git` will provide most detailed diagnostics info, but also obviously involves sharing the entire local history of the repository.
    Mostly recommended for open source projects.

    In case the tgz-ed repository is too large to share via GitHub web upload, you can try either pushing the repository as a file onto a branch,
    or actually sharing the entire `.git` folder as a repository on GitHub, so basically doing:

    ```bash
    cd .git/
    git init
    git add -a
    git commit -m 'git-machete v?.?.? issue #...'
    git remote add origin ...URL...
    git push origin master
    ```

Obviously sharing more data will make it easier to investigate the issue, but also involves sharing more project data.
Even if you go for the option 1. or 2., it might be good to make a local copy of `.git` folder since `git machete` heavily relies on branch reflogs (`.git/logs/refs/`)
that change as state of the repository changes, get expired due to `git gc` etc. which can make it hard to reproduce the original bug after some time passes.
