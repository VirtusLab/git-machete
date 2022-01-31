FROM python:3-alpine
SHELL ["/bin/sh", "-e", "-o", "pipefail", "-u", "-x", "-c"]
RUN apk add --no-cache git

COPY . /tmp/input/
WORKDIR /tmp/input/
RUN find . | sort
RUN \
  export PYTHONDONTWRITEBYTECODE=1; \
  python setup.py install; \
  git machete --version; \
  rm -rf /tmp/input/

WORKDIR /repo
VOLUME /repo
ENTRYPOINT ["git", "machete"]
