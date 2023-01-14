ARG ubuntu_version
FROM ubuntu:${ubuntu_version}
SHELL ["/bin/bash", "-e", "-o", "pipefail", "-u", "-x", "-c"]

ARG launchpad_username
# See https://github.com/phusion/baseimage-docker/issues/58 for why DEBIAN_FRONTEND=noninteractive is needed (20.04-only issue)
RUN \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y git gpg-agent software-properties-common; \
    add-apt-repository ppa:$launchpad_username/git-machete; \
    apt-get autoremove --purge -y gpg-agent software-properties-common

COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]
