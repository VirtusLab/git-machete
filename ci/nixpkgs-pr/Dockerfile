FROM nixos/nix

RUN nix-env -i bash curl git hub jq

COPY pr-description.md entrypoint.sh /root/
RUN chmod +x /root/entrypoint.sh
ENTRYPOINT /root/entrypoint.sh

WORKDIR /root/nixpkgs
