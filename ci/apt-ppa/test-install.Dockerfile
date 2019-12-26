FROM ubuntu

RUN apt-get update && apt-get install -y git software-properties-common
RUN add-apt-repository ppa:virtuslab/git-machete

COPY test-install-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]
