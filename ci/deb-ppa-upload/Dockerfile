FROM ubuntu:20.04
SHELL ["/bin/bash", "-e", "-o", "pipefail", "-u", "-x", "-c"]

# See https://github.com/phusion/baseimage-docker/issues/58 for why DEBIAN_FRONTEND=noninteractive is needed.
RUN \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      debhelper devscripts fakeroot dh-python gawk python3-all python3-paramiko python3-setuptools sudo; \
    rm -rfv /var/lib/apt/lists/*

COPY dput.cf.envsubst entrypoint.sh gpg-wrapper.sh release-notes-to-changelog.awk run.sh /
RUN chmod a+r /dput.cf.envsubst /release-notes-to-changelog.awk
RUN touch /etc/dput.cf
RUN chmod a+w /etc/dput.cf
RUN chmod a+rx /entrypoint.sh /gpg-wrapper.sh /run.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/run.sh"]
# One extra level under / is needed, since Debian packaging tools will write files
# in the parent directory of current working directory.
WORKDIR /git-machete/mount/
RUN chmod -R a+rwx /git-machete
