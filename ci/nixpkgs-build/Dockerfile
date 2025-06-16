FROM nixos/nix:2.5.1

RUN nix-env -i bash curl git gnused
SHELL ["bash", "-e", "-o", "pipefail", "-u", "-x", "-c"]

COPY entrypoint.sh /root/
RUN chmod +x /root/entrypoint.sh
CMD /root/entrypoint.sh

WORKDIR /root/nixpkgs
ENV EXPRESSION_PATH=pkgs/by-name/gi/git-machete/package.nix
