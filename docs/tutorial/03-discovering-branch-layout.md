# Tutorial - Part 3: Discovering branch layout

To function correctly, `git-machete` needs to know how your branches are related.
It stores this information in a simple text file: `.git/machete`.

### The `.git/machete` file

This file defines the hierarchy of your branches.
It looks something like this:
```text
master
  develop
    feature-1
    feature-2
      feature-2-bugfix
```
Indentation defines the parent-child relationship.
In this example, `develop` is a child of `master`, and `feature-1` and `feature-2` are children of `develop`.

### Automatic discovery

If you have an existing repository with many branches, you don't have to create this file manually.
Run:
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
This opens `.git/machete` in your editor.
You can reorder branches, change their parents by changing indentation, or add/remove branches.

Alternatively, you can add the current branch to the layout using:
```shell
git machete add <parent-branch-name>
```

> Tip — you only need to list the branches you want `git-machete` to manage.
> You can leave out short-lived or irrelevant branches.

Now that we have a layout, let's see how `git-machete` visualizes the state of these branches.

[< Previous: Installation and setup](02-installation-setup.md) | [Next: Understanding status >](04-understanding-status.md)
