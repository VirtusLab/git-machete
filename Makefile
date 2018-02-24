BINDIR ?= /usr/local/bin
BINFILE = git-machete

COMPDIR ?= /etc/bash_completion.d
COMPFILE = git-machete-prompt

.PHONY: all install uninstall

all:
	@echo "usage: make install"
	@echo "       make uninstall"

install:
	mkdir -p $(BINDIR)
	install -m 0755 $(BINFILE) $(BINDIR)
	mkdir -p $(COMPDIR)
	install -m 0644 $(COMPFILE) $(COMPDIR)

uninstall:
	test -d $(BINDIR)
	cd $(BINDIR)
	rm -f $(BINDIR)/$(BINFILE)
	test -d $(COMPDIR)
	cd $(COMPDIR)
	rm -f $(COMPDIR)/$(COMPFILE)

