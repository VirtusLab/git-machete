FROM nixos/nix:latest

# 1. Enable Flakes/Nix-Command
RUN echo "experimental-features = nix-command flakes" >> /etc/nix/nix.conf

# 2. Install sed, nix-update, and CA Certificates (for SSL)
RUN nix-env -iA nixpkgs.cacert nixpkgs.gnused nixpkgs.nix-update

# 3. Point SSL variables to the Nix-provided certs
ENV SSL_CERT_FILE=/root/.nix-profile/etc/ssl/certs/ca-bundle.crt
ENV NIX_SSL_CERT_FILE=/root/.nix-profile/etc/ssl/certs/ca-bundle.crt

COPY entrypoint.sh /root/
RUN chmod +x /root/entrypoint.sh
CMD /root/entrypoint.sh

WORKDIR /root/nixpkgs
ENV EXPRESSION_PATH=pkgs/by-name/gi/git-machete/package.nix
