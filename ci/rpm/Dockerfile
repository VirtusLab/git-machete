FROM fedora:35 as base
SHELL ["/bin/bash", "-e", "-o", "pipefail", "-u", "-x", "-c"]

RUN dnf install -y python3-pip rpm-build
RUN ln -s /usr/bin/python3 /usr/local/bin/python

FROM base AS circle_ci
COPY entrypoint.sh /root/
RUN chmod +x /root/entrypoint.sh
CMD ["/root/entrypoint.sh"]
WORKDIR /root/git-machete

FROM base AS local
ARG user_id
ARG group_id
RUN set -x \
    && [ ${user_id:-0} -ne 0 ] \
    && [ ${group_id:-0} -ne 0 ] \
    # sometimes the given `group_id` is already taken and `addgroup` raises an error, so let's check its existence first
    && (getent group $group_id || groupadd --gid=${group_id} ci-user) \
    && useradd -l -u ${user_id} -g $group_id ci-user \
    && install -d -m 0755 -o ci-user -g $group_id /home/ci-user
USER ci-user
COPY --chown=ci-user:ci-user entrypoint.sh /home/ci-user/
RUN chmod +x ~/entrypoint.sh
CMD ["/home/ci-user/entrypoint.sh"]
WORKDIR /home/ci-user/git-machete
