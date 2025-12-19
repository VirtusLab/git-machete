# Tutorial - Part 1: Introduction

This tutorial covers the core features of `git-machete`.

`git-machete` is a robust tool that **simplifies your git workflows**.
It's particularly useful when you work with many branches, stacked pull requests, or a rebase-focused workflow.

### Why git-machete?

In modern software development, we often work on multiple features simultaneously.
Sometimes these features depend on each other, leading to a "chain" of branches:

`develop` -> `feature-1` -> `feature-2` -> `feature-3`

When `develop` moves forward, or when you update `feature-1` based on review comments, you suddenly have to rebase `feature-2` onto `feature-1`, and then `feature-3` onto `feature-2`.
Doing this manually is tedious and error-prone.

`git-machete` provides:
* Bird's eye view — see all your branches and their relationships at a glance.
* Automatic status — know instantly which branches are in sync, which need a rebase, and which are merged.
* Simplified syncing — rebase, push, and pull multiple branches with a single command.
* Safe cleanups — easily remove branches that have already been merged.

### What's in this tutorial?

This tutorial is divided into bite-sized parts that will take you through the most important features of git-machete.
We'll cover:
1.  Installation and setup
2.  Discovering branch layout
3.  Understanding status
4.  Navigating between branches
5.  Updating a branch
6.  Automating workflow with traverse
7.  Fast-forwarding with advance
8.  Cleaning up with slide-out
9.  GitHub/GitLab integration

The first step is to get `git-machete` installed.

[Next: Installation & Setup >](02-installation-setup.md)
