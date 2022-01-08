FROM python:3-alpine
RUN apk update
RUN apk add git

ARG pypi_host
ARG version
RUN pip install --index-url=https://$pypi_host/simple/ git-machete==$version
RUN git machete --version

WORKDIR /repo
VOLUME /repo
ENTRYPOINT ["git", "machete"]
