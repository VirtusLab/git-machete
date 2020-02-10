FROM nixos/nix

RUN nix-env -i curl git jq

WORKDIR /root
RUN git clone --depth=1 https://github.com/NixOS/nixpkgs.git
RUN git clone --depth=1 https://github.com/github/hub.git

RUN set -x \
    && cd /root/hub/ \
    && nix-env -i bash go gnumake \
    && make bin/hub \
    && cp bin/hub /usr/local/bin \
    && mkdir -p /usr/local/bin \
    && nix-env -e bash go gnumake \
    && nix-collect-garbage -d \
    && cd /root \
    && rm -r hub/
ENV PATH=$PATH:/usr/local/bin
RUN hub --version

WORKDIR /root/nixpkgs
ARG git_machete_version=2.12.10
RUN set -o pipefail -u \
    && pypi_json=$(curl -s https://pypi.org/pypi/git-machete/v$git_machete_version/json) \
    && pypi_url=$(echo "$pypi_json" | jq --raw-output '.urls | map(select(.packagetype == "sdist")) | .[0].url') \
    && set -x \
    && tarball_sha256=$(nix-prefetch-url --type sha256 "$pypi_url") \
    && expression_path=pkgs/applications/version-management/git-and-tools/git-machete/default.nix \
    && sed -i "s/version = \".*\";/version = \"$git_machete_version\";/" $expression_path \
    && sed -i "s/sha256 = \".*\";/sha256 = \"$tarball_sha256\";/" $expression_path
RUN nix-build -A gitAndTools.git-machete
RUN nix-env -f . -iA gitAndTools.git-machete
RUN set -u -x \
    && installed_version=$(git machete --version) \
    && [ ${installed_version/git-machete version/} = $git_machete_version ]
