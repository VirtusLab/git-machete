ARG python_version
FROM python:${python_version}-alpine
# Required since the earlier versions of git assume the location of python to be /usr/bin/python during the build.
RUN ln -s /usr/local/bin/python /usr/bin/python

ARG git_version
RUN set -x \
    && apk add --no-cache --virtual git-build-deps  alpine-sdk autoconf gettext wget zlib-dev \
    && wget -q https://github.com/git/git/archive/v$git_version.tar.gz \
    && tar xzf v$git_version.tar.gz \
    && rm v$git_version.tar.gz \
    && cd git-$git_version/ \
    && make configure \
    && ./configure \
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

ARG user_id
ARG group_id
RUN set -x \
    && [ ${user_id:-0} -ne 0 ] \
    && [ ${group_id:-0} -ne 0 ] \
    && addgroup --gid=${group_id} ci-user \
    && adduser --uid=${user_id} --ingroup=ci-user --disabled-password ci-user
USER ci-user
ENV PATH=$PATH:/home/ci-user/.local/bin/
COPY --chown=ci-user:ci-user entrypoint.sh /home/ci-user/
RUN chmod +x ~/entrypoint.sh
CMD ["/home/ci-user/entrypoint.sh"]
WORKDIR /home/ci-user/git-machete
