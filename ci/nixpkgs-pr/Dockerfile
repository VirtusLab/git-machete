FROM nixos/nix

RUN nix-env -i autoconf bash curl git hub jq

COPY *.md entrypoint.sh /root/
RUN chmod +x /root/entrypoint.sh
ENTRYPOINT /root/entrypoint.sh

WORKDIR /root/nixpkgs
