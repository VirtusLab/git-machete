FROM ubuntu:latest

RUN sudo apt-get install -y software-properties-common && sudo add-apt-repository ppa:virtuslab/git-machete && sudo apt-get update && sudo apt-get install -y python3-git-machete 


 

