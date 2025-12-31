# Tutorial - Part 2: Installation and setup

### Installation

The recommended way to install `git-machete` depends on your setup.

#### macOS
On macOS, we recommend using Homebrew.
```shell
brew install git-machete
```

#### pip
On almost any system, if you have Python and `pip` installed, the following should work:
```shell
pip install --user git-machete
```

For other common installation methods (Windows, Nix, conda, etc.), see the [README](../../README.md), _Install_ section.
For the complete list of known wrapper packages for git-machete, see [PACKAGES](../../PACKAGES.md).

### Shell completions

`git-machete` comes with shell completion support.
If you installed via Homebrew, it might already be set up.
Otherwise, add the following to your shell configuration file (`.bashrc`, `.zshrc`, or `config.fish`):

Bash: `source <(git machete completion bash)`
Zsh: `source <(git machete completion zsh)`
Fish: `git machete completion fish | source`

### Shell aliases

For a smoother experience, you might want to set up some shell aliases to save typing.
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
