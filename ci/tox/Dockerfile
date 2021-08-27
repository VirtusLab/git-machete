ARG python_version
FROM python:${python_version}-alpine
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

# Pass build argument to CHECK_COVERAGE environment variable that is used to
# determine tox environment list in 'entrypoint.sh'.
ARG check_coverage
ENV CHECK_COVERAGE=${check_coverage}

# Pass build argument to BUILD_DOCS environment variable that is used to
# determine where to run tox enviornment that builds documentation.
ARG build_docs
ENV BUILD_DOCS=${build_docs}

ARG user_id
ARG group_id
RUN set -x \
    && [ ${user_id:-0} -ne 0 ] \
    && [ ${group_id:-0} -ne 0 ] \
    # sometimes given group_id is already taken and addgroup outputs error, so let's check it's existence first
    && (getent group $group_id || addgroup --gid=${group_id} ci-user) \
    && adduser --uid=${user_id} --ingroup=$(getent group $group_id | cut -d: -f1) --disabled-password ci-user
USER ci-user
RUN $PYTHON -m pip install --user tox
ENV PATH=$PATH:/home/ci-user/.local/bin/
COPY --chown=ci-user:ci-user entrypoint.sh /home/ci-user/
RUN chmod +x ~/entrypoint.sh
CMD ["/home/ci-user/entrypoint.sh"]
WORKDIR /home/ci-user/git-machete
