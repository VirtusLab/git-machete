FROM nixos/nix

RUN nix-env -i bash curl git jq

WORKDIR /root
RUN set -x \
    && git clone --depth=1 https://github.com/github/hub.git \
    && cd /root/hub/ \
    && nix-env -i go gnumake \
    && make bin/hub \
    && cp bin/hub /usr/local/bin \
    && mkdir -p /usr/local/bin \
    && nix-env -e go gnumake \
    && nix-collect-garbage -d \
    && cd /root \
    && rm -r hub/
ENV PATH=$PATH:/usr/local/bin
RUN hub --version

RUN mkdir /root/nixpkgs
WORKDIR /root/nixpkgs

COPY pr-description.md entrypoint.sh /root/
RUN chmod +x /root/entrypoint.sh
ENTRYPOINT /root/entrypoint.sh
