FROM ubuntu:latest

RUN apt-get update \
  && apt-get install -y software-properties-common \
  && add-apt-repository ppa:virtuslab/git-machete \
  && apt-get update \
  && apt-get install -y python3-git-machete
