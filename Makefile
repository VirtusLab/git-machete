BINDIR = /usr/local/bin
BINFILE = git-machete

.PHONY: all build install uninstall clean

all:
	@echo "usage: make install"
	@echo "       make uninstall"

build:
	install -m 0755 git_machete/cmd.py git-machete

install: build
	install -d $(BINDIR)
	install -m 0755 $(BINFILE) $(BINDIR)

uninstall:
	rm -f $(BINDIR)/$(BINFILE)

clean:
	rm -rf .eggs/ .stestr/ .tox/ build/ *.egg-info/ AUTHORS ChangeLog
