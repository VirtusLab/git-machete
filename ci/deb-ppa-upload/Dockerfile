FROM ubuntu:20.04

# See https://github.com/phusion/baseimage-docker/issues/58 for why DEBIAN_FRONTEND=noninteractive is needed.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y debhelper devscripts fakeroot dh-python gawk python3-all python3-paramiko python3-setuptools \
    && rm -rfv /var/lib/apt/lists/*

ARG user_id
ARG group_id

RUN set -x \
    && [ ${user_id:-0} -ne 0 ] \
    && [ ${group_id:-0} -ne 0 ] \
    && groupadd -g ${group_id} ci-user \
    && useradd -l -u ${user_id} -g ci-user ci-user \
    && install -d -m 0755 -o ci-user -g ci-user /home/ci-user

USER ci-user

RUN install -d -m 0700 ~/.gnupg/ ~/.gnupg/private-keys-v1.d/ ~/.ssh/

COPY dput.cf /etc/

COPY --chown=ci-user:ci-user gpg-sign.sh /home/ci-user/
RUN chmod +x ~/gpg-sign.sh

COPY --chown=ci-user:ci-user release-notes-to-changelog.awk /home/ci-user/

COPY --chown=ci-user:ci-user entrypoint.sh /home/ci-user/
RUN chmod +x ~/entrypoint.sh
CMD ["/home/ci-user/entrypoint.sh"]

WORKDIR /home/ci-user/git-machete
