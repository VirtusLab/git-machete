ARG python_version
FROM python:${python_version}-alpine as base
SHELL ["/bin/sh", "-e", "-o", "pipefail", "-u", "-x", "-c"]
# Required since the earlier versions of git assume the location of python to be /usr/bin/python during the build.
RUN ln -s /usr/local/bin/python /usr/bin/python

ARG git_version
RUN set -x \
    && apk add --no-cache --virtual=git-build-deps alpine-sdk autoconf gettext wget zlib-dev \
    && wget -q https://github.com/git/git/archive/v$git_version.tar.gz \
    && tar xzf v$git_version.tar.gz \
    && rm v$git_version.tar.gz \
    && cd git-$git_version/ \
    && make configure \
    && ./configure \
    && sed -i 's/#warning .*//' /usr/include/sys/poll.h  `# to reduce amount of spam warnings in logs` \
    && make \
    && make install \
    && cd .. \
    && rm -r git-$git_version/ \
    && git --version \
    && apk del git-build-deps \
    && rm -rfv /usr/local/bin/git-shell /usr/local/share/git-gui/ \
    && cd /usr/local/libexec/git-core/ \
    && rm -fv git-credential-* git-daemon git-fast-import git-http-backend git-imap-send git-remote-testsvn git-shell

ARG python_version
ENV PYTHON_VERSION=${python_version}
ENV PYTHON=python${python_version}
RUN apk add --no-cache gcc musl-dev # both packages are required to install mypy

FROM base AS circle_ci
RUN $PYTHON -m pip install tox
ENV PATH=$PATH:/root/.local/bin/
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
    && (getent group $group_id || addgroup --gid=${group_id} ci-user) \
    && adduser --uid=${user_id} --ingroup=$(getent group $group_id | cut -d: -f1) --disabled-password ci-user
USER ci-user
RUN $PYTHON -m pip install --user tox
ENV PATH=$PATH:/home/ci-user/.local/bin/
COPY --chown=ci-user:ci-user entrypoint.sh /home/ci-user/
RUN chmod +x ~/entrypoint.sh
CMD ["/home/ci-user/entrypoint.sh"]
WORKDIR /home/ci-user/git-machete
