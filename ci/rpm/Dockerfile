FROM fedora:35
SHELL ["/bin/bash", "-e", "-o", "pipefail", "-u", "-x", "-c"]

RUN dnf install -y python3-pip rpm-build

COPY entrypoint.sh run.sh /
RUN chmod +x /entrypoint.sh /run.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/run.sh"]
WORKDIR /git-machete
