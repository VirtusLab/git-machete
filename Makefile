PREFIX ?= /usr/local
EXEC_PREFIX ?= $(PREFIX)
BINDIR ?= $(EXEC_PREFIX)/bin

EXEC_FILES = git-machete

.PHONY: all install uninstall

all:
	@echo "usage: make install"
	@echo "       make uninstall"

install:
	mkdir -p $(BINDIR)
	install -m 0755 $(EXEC_FILES) $(BINDIR)

uninstall:
	test -d $(BINDIR) && \
	cd $(BINDIR) && \
	rm -f $(EXEC_FILES)

