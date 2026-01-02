FROM nixos/nix:latest

RUN nix-env -iA nixpkgs.gnused nixpkgs.nix-update

COPY entrypoint.sh /root/
RUN chmod +x /root/entrypoint.sh
CMD /root/entrypoint.sh

WORKDIR /root/nixpkgs
ENV EXPRESSION_PATH=pkgs/by-name/gi/git-machete/package.nix
