###### Motivation for this change
Update to latest upstream version

###### Things done
 * [ ]  Tested using sandboxing ([nix.useSandbox](http://nixos.org/nixos/manual/options.html#opt-nix.useSandbox) on NixOS, or option `sandbox` in [`nix.conf`](http://nixos.org/nix/manual/#sec-conf-file) on non-NixOS linux)
 * Built on platform(s)

   * [x]  NixOS
   * [ ]  macOS
   * [ ]  other Linux distributions
 * [ ]  Tested via one or more NixOS test(s) if existing and applicable for the change (look inside [nixos/tests](https://github.com/NixOS/nixpkgs/blob/master/nixos/tests))
 * [ ]  Tested compilation of all pkgs that depend on this change using `nix-shell -p nix-review --run "nix-review wip"`
 * [x]  Tested execution of all binary files (usually in `./result/bin/`)
 * [ ]  Determined the impact on package closure size (by running `nix path-info -S` before and after)
 * [ ]  Ensured that relevant documentation is up to date
 * [x]  Fits [CONTRIBUTING.md](https://github.com/NixOS/nixpkgs/blob/master/.github/CONTRIBUTING.md).

###### Notify maintainers
`cc @worldofpeace @tfc @jtraue` **TODO un-``-ize**
