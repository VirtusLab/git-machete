# Tutorial - Part 1: Introduction

This tutorial covers the core features of `git-machete`.

`git-machete` is a robust tool that simplifies your git workflows.
It's particularly useful when you work with many branches and stacked pull requests.

### Why git-machete?

In modern software development, we often work on multiple features simultaneously.
Sometimes these features depend on each other, leading to a "chain" of branches:

`feature-3` -> `feature-2` -> `feature-1` -> `develop`

A very common case is when you have a refactor or a bugfix that a feature depends on before it can be merged.
Stacking branches allows you to continue working on your feature while the supporting changes are under review:

`feature` -> `refactor` -> `bugfix` -> `develop`

When `develop` moves forward, or when you update `bugfix` based on review comments,
you suddenly have to rebase `refactor` onto `bugfix`, and then `feature` onto `refactor`.
Doing this manually is tedious and error-prone.

`git-machete` provides:
* Bird's eye view — see all your branches and their relationships at a glance.
* Automatic `status` — know instantly which branches are in sync, which need a rebase, and which are merged.
* Simplified syncing — rebase, push, and pull multiple branches with a single command.
* Integration with GitHub and GitLab - keep PR structure & descriptions in sync with your local state

### What's in this tutorial?

This tutorial is divided into bite-sized parts that will take you through the most important features of git-machete.
We'll cover:
1.  Installation and setup
2.  Discovering branch layout
3.  Understanding `status`
4.  Using branch annotations
5.  Navigating between branches
6.  Updating a branch with a rebase
7.  Squashing and reapplying
8.  Automating workflow with `traverse`
9.  Fast-forwarding with `advance`
10. Cleaning up with `slide-out`
11. GitHub/GitLab integration

The first step is to get `git-machete` installed.

[Next: Installation & Setup >](02-installation-setup.md)
