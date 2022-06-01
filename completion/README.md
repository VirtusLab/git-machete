## Bash

### Mac (via Homebrew)

Make sure you have bash completion installed (with `brew install bash-completion`).

`brew install git-machete` automatically installs bash completion files for `git machete`.

If the bash completion doesn't work:
1. Install git bash completions with `brew install git bash-completion`
2. Add the below code to `~/.bash_profile` and reload the shell
```shell script
[ -f /usr/local/etc/bash_completion ] && . /usr/local/etc/bash_completion \
  || # if not found in /usr/local/etc, try the brew --prefix location
    {
      [ -f "$(brew --prefix)/etc/bash_completion.d/git-completion.bash" ] \
        && . $(brew --prefix)/etc/bash_completion.d/git-completion.bash
      [ -f "$(brew --prefix)/etc/bash_completion.d/git-machete.completion.bash" ] \
        && . $(brew --prefix)/etc/bash_completion.d/git-machete.completion.bash
    }
```


### Linux

1. In a non-minimal installation of Linux, bash completion should be available.
2. Place the completion script in `/etc/bash_completion.d/`.

```shell script
sudo curl -L https://raw.githubusercontent.com/VirtusLab/git-machete/master/completion/git-machete.completion.bash -o /etc/bash_completion.d/git-machete
```


## Zsh

### Linux/Mac: with [oh-my-zsh](https://ohmyz.sh/) shell

```shell script
$ mkdir -p ~/.oh-my-zsh/custom/plugins/git-machete/
$ curl -L https://raw.githubusercontent.com/VirtusLab/git-machete/master/completion/git-machete.completion.zsh -o ~/.oh-my-zsh/custom/plugins/git-machete/git-machete.plugin.zsh
```

Add `git-machete` to the plugins list in `~/.zshrc` to run autocompletion within the oh-my-zsh shell.
In the following example, `...` represents other zsh plugins you may have installed.

```shell script
plugins=(... git-machete
)
```

#### Workarounds for Zsh on Mac

On Mac, unfortunately there might be a problem that `git machete` subcommands still don't complete even when the zsh plugin is active.
This issue also affects other non-standard `git` subcommands like `git flow` and `git lfs`.
To work the issue around, first establish how `git` is installed in your system.
```shell script
which git
```

If `git` resolves to `/usr/bin/git`, then likely `git` is the default installation provided in Mac OS.
As a workaround, add the following line directly at the end of `~/.zshrc`:
```shell script
source ~/.oh-my-zsh/custom/plugins/git-machete/git-machete.plugin.zsh
```
and reload the shell.

If `git` resolves to `/usr/local/bin/git`, then likely `git` has been installed via `brew`.
Up to our current knowledge, workaround is much harder to provide in such scenario.

One option is to `brew uninstall git` and then use the solution for Mac's default `git` provided above,
but that's likely undesired since `git` shipped with Mac OS is almost always an older version than what's available via `brew`.

Another, less intrusive workaround is to make sure that the zsh `_git` function
is NOT taken from brew-git's `/usr/local/share/zsh/site-functions/_git`,
but instead from `/usr/share/zsh/5.7.1/functions/_git` (zsh version path fragment can be different from `5.7.1`).
Add the following at the end of `~/.zshrc`:
```shell script
source /usr/share/zsh/5.7.1/functions/_git  # or other zsh version instead of 5.7.1, depending on what's available in the system
```
and reload the shell.


### Linux/Mac: without oh-my-zsh shell

1. Place the completion script in your `/path/to/zsh/completion` (typically `~/.zsh/completion/`):

```shell script
$ mkdir -p ~/.zsh/completion
$ curl -L https://raw.githubusercontent.com/VirtusLab/git-machete/master/completion/git-machete.completion.zsh -o ~/.zsh/completion/_git-machete
```

2. Include the directory in your `$fpath` by adding in `~/.zshrc`:

```shell script
fpath=(~/.zsh/completion $fpath)
```

3. Make sure `compinit` is loaded or do it by adding in `~/.zshrc`:

```shell script
autoload -Uz compinit && compinit -i
```

4. Then reload your shell:

```shell script
exec $SHELL -l
```

## Fish

### Mac (via Homebrew)
Please look at the section about [installation via Homebrew](../README.md#using-homebrew-macos).
``brew install git-machete`` automatically installs fish completion files for ``git machete``.

### Linux

Place the completion script in `/path/to/fish/completions/` (typically `~/.config/fish/completions/git-machete.fish`).

```shell script
mkdir -p ~/.config/fish/completions
curl -L https://raw.githubusercontent.com/VirtusLab/git-machete/master/completion/git-machete.fish -o ~/.config/fish/completions/git-machete.fish
echo "source ~/.config/fish/completions/git-machete.fish >/dev/null" >> ~/.config/fish/config.fish
```
