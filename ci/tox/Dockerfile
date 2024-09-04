ARG python_version
FROM python:${python_version}-alpine
SHELL ["/bin/sh", "-e", "-o", "pipefail", "-u", "-x", "-c"]
# Required since the earlier versions of git assume the location of python to be /usr/bin/python during the build.
RUN ln -s /usr/local/bin/python /usr/bin/python

ARG git_version
RUN \
    apk add --no-cache --virtual=git-build-deps alpine-sdk autoconf gettext wget zlib-dev; \
    wget -q https://github.com/git/git/archive/v$git_version.tar.gz; \
    tar xzf v$git_version.tar.gz; \
    rm v$git_version.tar.gz; \
    cd git-$git_version/; \
    make configure; \
    ./configure; \
    sed -i 's/#warning .*//' /usr/include/sys/poll.h  `# to reduce amount of spam warnings in logs`; \
    make; \
    make install; \
    cd ..; \
    rm -r git-$git_version/; \
    git --version; \
    apk del git-build-deps; \
    rm -rfv /usr/local/bin/git-shell /usr/local/share/git-gui/; \
    cd /usr/local/libexec/git-core/; \
    rm -fv git-credential-* git-daemon git-fast-import git-http-backend git-imap-send git-remote-testsvn git-shell

ARG python_version
ENV PYTHON_VERSION=${python_version}
ENV PYTHON=python${python_version}
RUN apk add --no-cache gcc musl-dev  # packages required to install mypy
RUN $PYTHON -m pip install tox setuptools

RUN apk add --no-cache bash sudo  # packages required to run the entrypoint script
ENV PATH=$PATH:/root/.local/bin/
COPY entrypoint.sh run.sh /
RUN chmod a+rx /entrypoint.sh /run.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/run.sh"]
WORKDIR /git-machete
