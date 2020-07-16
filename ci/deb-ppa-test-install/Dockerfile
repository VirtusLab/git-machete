ARG ubuntu_version
FROM ubuntu:${ubuntu_version}

# See https://github.com/phusion/baseimage-docker/issues/58 for why DEBIAN_FRONTEND=noninteractive is needed (20.04-only issue)
RUN set -x \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y git software-properties-common \
    && add-apt-repository ppa:virtuslab/git-machete \
    && apt-get autoremove --purge -y software-properties-common \
    && rm -rfv /var/lib/apt/lists/*

COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]
