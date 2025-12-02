
# bump base image: 1

FROM archlinux:base-devel
# https://wiki.archlinux.org/title/System_maintenance#Partial_upgrades_are_unsupported
RUN pacman -Syu --noconfirm git

RUN useradd -m builder && \
    echo "builder ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/builder && \
    chmod 0440 /etc/sudoers.d/builder
USER builder
WORKDIR /home/builder

COPY --chown=builder entrypoint.sh .
RUN chmod +x entrypoint.sh
CMD /home/builder/entrypoint.sh
