# Overview

...

## Expected behavior/command output

...

## Actual behavior/command output

...

## `git` and `git machete` versions

```
git --version

git machete --version

```

## Please `cp -r .git .git.bak`!

Please back-up your `.git` folder at its current state for the issue to be reproducible in the future!
`git machete` heavily relies on branch reflogs (`.git/logs/refs/`) that change as state of the repository changes, get expired due to `git gc` etc.

## Additional diagnostics info

Depending on your NDAs/level of confidentiality of the project stored in your repository, you can also include **one of the 3 following variants** of diagnostics information:

1. `--verbose` &mdash; executed git commands

    `git machete --verbose <problematic-command>` (stdout+stderr)

    If it comes to repository-specific data, this will only include commit hashes,
    names of local branches and their remote counterparts.
    No commit messages, file paths or file contents will be included.

2. `--debug` &mdash; executed git commands + their outputs and other detailed logging information

    `git machete --debug <problematic-command>` (stdout+stderr)

    If it comes to repository-specific data, this will include names of local branches and their remote counterparts,
    their full logs (but only wrt. commit hashes) and their full reflogs (which typically include commit messages).
    No file paths or file contents will be included.

    Most notably, the **output of `git config --list` will be included**.
    There is a mechanism to redact away known tokens from remote URLs &mdash; but please verify this output yourself
    (`git config` will be among the first commands executed).

3. Ultimate knowledge - above + the `.git` folder

    `git machete --debug <problematic-command>` (stdout+stderr)

    AND

    `tar czvf dotgit.tgz .git/`

    Sharing contents of `.git` will provide most detailed diagnostics info,
    but also obviously involves sharing the entire local history of the repository. Mostly recommended for open source projects.

    In case the tgz-ed repository is too large to share via GitHub web upload,
    you can try either pushing the tgz-ed repository as a file onto a branch,
    or actually sharing the entire non-tgz-ed `.git` folder as a repository on GitHub, so basically doing:

    ```shell script
    cd .git/
    git init
    git add -a
    git commit -m 'git-machete v?.?.? issue #...'
    git remote add origin ...URL...
    git push origin master
    ```

Obviously sharing more data will make it easier to investigate the issue, but also involves sharing more project data.
