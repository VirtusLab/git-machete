# Tutorial - Part 2: Installation & Setup

Before we can use `git-machete`, we need to install it.

### Installation

The recommended way to install `git-machete` depends on your operating system:

#### macOS / Linux (Homebrew)
```shell
brew install git-machete
```

#### Python / Pip (Cross-platform)
```shell
pip install --user git-machete
```

For other installation methods (Windows, Nix, Arch Linux, etc.), see the [full installation guide](../../PACKAGES.md).

### Shell Completions

`git-machete` comes with excellent shell completion support.
If you installed via Homebrew, it might already be set up.
Otherwise, add the following to your shell configuration file (`.bashrc`, `.zshrc`, or `config.fish`):

**Bash:** `source <(git machete completion bash)`
**Zsh:** `source <(git machete completion zsh)`
**Fish:** `git machete completion fish | source`

### Verifying Installation

Once installed, verify it by running:
```shell
git machete version
```

If you see a version number, you're good to go!
In the next part, we'll see how to introduce `git-machete` to your existing project.

[< Previous: Introduction](01-introduction.md) | [Next: Discovering Branch Layout >](03-discovering-branch-layout.md)
