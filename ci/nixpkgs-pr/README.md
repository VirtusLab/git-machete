## Creation of PR to NixOS/nixpkgs from local machine

```bash
cd ci/nixpkgs-pr/
. export-github-config
VERSION=2.13.2 ./local-run.sh  # pass the version to release, without the leading 'v'
```
