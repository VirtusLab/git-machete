# Tutorial - Part 2: Installation and setup

Before we can use `git-machete`, we need to install it.

### Installation

The recommended way to install `git-machete` depends on your setup.

#### macOS
On macOS, we recommend using Homebrew.
```shell
brew install git-machete
```

#### pip
If you have Python and `pip` installed, it should work on almost any system.
```shell
pip install --user git-machete
```

For other installation methods (Windows, Nix, Arch Linux, etc.), see the [full installation guide](../../PACKAGES.md).

### Shell completions

`git-machete` comes with excellent shell completion support.
If you installed via Homebrew, it might already be set up.
Otherwise, add the following to your shell configuration file (`.bashrc`, `.zshrc`, or `config.fish`):

Bash: `source <(git machete completion bash)`
Zsh: `source <(git machete completion zsh)`
Fish: `git machete completion fish | source`

### Verifying installation

Once installed, verify it by running:
```shell
git machete version
```

In the next part, we'll see how to introduce `git-machete` to your existing project.

[< Previous: Introduction](01-introduction.md) | [Next: Discovering branch layout >](03-discovering-branch-layout.md)
