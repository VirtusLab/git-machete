FROM nixos/nix:latest

# 1. Enable Flakes/Nix-Command
RUN echo "experimental-features = nix-command flakes" >> /etc/nix/nix.conf

# 2. Install sed, nix-update, and CA Certificates (for SSL)
RUN nix-env -iA nixpkgs.cacert nixpkgs.gnused nixpkgs.nix-update

# 3. Point SSL variables to the Nix-provided certs
ENV SSL_CERT_FILE=/root/.nix-profile/etc/ssl/certs/ca-bundle.crt
ENV NIX_SSL_CERT_FILE=/root/.nix-profile/etc/ssl/certs/ca-bundle.crt

WORKDIR /work
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
