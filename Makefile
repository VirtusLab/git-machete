BINDIR = /usr/local/bin
BINFILE = git-machete

COMPDIR = /etc/bash_completion.d
COMPDIR2 = /usr/local/etc/bash_completion.d
COMPFILE = git-machete-prompt

.PHONY: all install uninstall

all:
	@echo "usage: make install"
	@echo "       make uninstall"

install:
	install -d $(BINDIR)
	install -m 0755 $(BINFILE) $(BINDIR)
	install -d $(COMPDIR)
	install -m 0644 $(COMPFILE) $(COMPDIR)
	install -d $(COMPDIR2)
	install -m 0644 $(COMPFILE) $(COMPDIR2)

uninstall:
	rm -f $(BINDIR)/$(BINFILE)
	rm -f $(COMPDIR)/$(COMPFILE)
	rm -f $(COMPDIR2)/$(COMPFILE)

