FROM ubuntu:18.04

RUN apt-get update && apt-get install -y git software-properties-common
RUN add-apt-repository ppa:virtuslab/git-machete

COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]
