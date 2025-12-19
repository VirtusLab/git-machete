# Tutorial - Part 1: Introduction

Welcome to the `git-machete` tutorial! 

`git-machete` is a robust tool that **simplifies your git workflows**. It's particularly useful when you work with many branches, stacked pull requests, or a "rebase-focused" workflow.

### Why git-machete?

In modern software development, we often work on multiple features simultaneously. Sometimes these features depend on each other, leading to a "chain" of branches:

`develop` -> `feature-1` -> `feature-2` -> `feature-3`

When `develop` moves forward, or when you update `feature-1` based on review comments, you suddenly have to rebase `feature-2` onto `feature-1`, and then `feature-3` onto `feature-2`. Doing this manually is tedious and error-prone.

`git-machete` provides:
*   **Bird's eye view**: See all your branches and their relationships at a glance.
*   **Automatic status**: Know instantly which branches are in sync, which need a rebase, and which are merged.
*   **Effortless syncing**: Rebase, push, and pull multiple branches with a single command.
*   **Safe cleanups**: Easily remove branches that have already been merged.

### What's in this tutorial?

This tutorial is divided into bite-sized parts that will take you from a git-machete novice to a power user. We'll cover:
1.  **Installation & Setup**
2.  **Discovering Branch Layout**
3.  **Understanding Status**
4.  **Navigating Between Branches**
5.  **Updating a Branch**
6.  **Automating Workflow with Traverse**
7.  **Fast-forwarding with Advance**
8.  **Cleaning Up with Slide-Out**
9.  **GitHub/GitLab Integration**

Ready to start? Let's get `git-machete` installed!

[Next: Installation & Setup >](02-installation-setup.md)
