FROM nixos/nix

ENV nix_flags="--extra-experimental-features nix-command --extra-experimental-features flakes"
RUN nix profile add $nix_flags nixpkgs#bash nixpkgs#curl nixpkgs#git nixpkgs#gnused
SHELL ["bash", "-e", "-o", "pipefail", "-u", "-x", "-c"]

COPY entrypoint.sh /root/
RUN chmod +x /root/entrypoint.sh
CMD /root/entrypoint.sh

WORKDIR /root/nixpkgs
ENV EXPRESSION_PATH=pkgs/by-name/gi/git-machete/package.nix
