# Tutorial - Part 2: Installation and setup

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

`git-machete` comes with a shell completion support.
If you installed via Homebrew, it might already be set up.
Otherwise, add the following to your shell configuration file (`.bashrc`, `.zshrc`, or `config.fish`):

Bash: `source <(git machete completion bash)`
Zsh: `source <(git machete completion zsh)`
Fish: `git machete completion fish | source`

### Shell aliases

For a smoother experience, you might want to set up some aliases in your shell.
A common practice is to alias `git` to `g` in your shell configuration:
```shell
alias g=git
```
You can also add a git alias for `machete`:
```shell
git config --global alias.m machete
```
This allows you to run `g m` instead of `git machete`.

[< Previous: Introduction](01-introduction.md) | [Next: Discovering and editing branch layout >](03-discovering-and-editing-branch-layout.md)
