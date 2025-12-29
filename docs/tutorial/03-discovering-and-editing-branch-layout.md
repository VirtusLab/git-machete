# Tutorial - Part 3: Discovering and editing branch layout

To function correctly, `git-machete` needs to know how your branches are related.
It stores this information in a simple text file: `.git/machete`.

### The `.git/machete` file

This file defines the hierarchy of your branches.
It looks something like this:
```text
develop
    allow-ownership-link
        build-chain
    call-ws
master
    hotfix/add-trigger
```
Indentation defines the parent-child relationship.
Both spaces and tabs are allowed, as long as they're used consistently.
In this example, `hotfix/add-trigger` is a child of `master`,
and `allow-ownership-link` and `call-ws` are children of `develop`.

### Automatic discovery

If you have an existing repository with many branches, you can automatically discover the layout by running:
```shell
git machete discover
```
`git-machete` will analyze your commit history and suggest a layout.
It will open your default editor so you can review and adjust the suggested layout.

### Manual editing

You can always change the layout by running:
```shell
git machete edit
```
This opens `.git/machete` in your default editor.
You can always override the editor with `GIT_MACHETE_EDITOR` env var, for example `export GIT_MACHETE_EDITOR=vim`.
You can reorder branches, change their parents by changing indentation, or add/remove branches.

Alternatively, you can add the current branch to the layout using:
```shell
git machete add <parent-branch-name>
```

You only need to list the branches you want `git-machete` to manage.
You can leave out short-lived or irrelevant branches.

[< Previous: Installation and setup](02-installation-setup.md) | [Next: Understanding `status` >](04-understanding-status.md)
