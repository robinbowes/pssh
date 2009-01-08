install-data-local: $(EXTRA_DIST)
	$(INSTALL_SCRIPT) -D bin/pssh @prefix@/bin/pssh
	$(INSTALL_SCRIPT) -D bin/pscp @prefix@/bin/pscp
	$(INSTALL_SCRIPT) -D bin/pnuke @prefix@/bin/pnuke
	$(INSTALL_SCRIPT) -D bin/prsync @prefix@/bin/prsync
	$(INSTALL_SCRIPT) -D bin/pslurp @prefix@/bin/pslurp
	$(INSTALL_DATA) -D lib/python/basethread.py \
					@prefix@/lib/python/basethread.py
	$(INSTALL_DATA) -D lib/python/psshutil.py \
					@prefix@/lib/python/psshutil.py

uninstall-local: $(EXTRA_DIST)
	rm -f @prefix@/bin/pssh
	rm -f @prefix@/bin/pscp
	rm -f @prefix@/bin/pnuke
	rm -f @prefix@/bin/prsync
	rm -f @prefix@/bin/pslurp
	rm -f @prefix@/lib/python/basethread.py
	rm -f @prefix@/lib/python/psshutil.py
	rm -f @prefix@/lib/python/basethread.pyc
	rm -f @prefix@/lib/python/psshutil.pyc
	rm -f @prefix@/lib/python/basethread.pyo
	rm -f @prefix@/lib/python/psshutil.pyo

EXTRA_DIST = bin/pssh \
             bin/pscp \
             bin/pnuke \
             bin/prsync \
             bin/pslurp \
             lib/python/psshutil.py \
             lib/python/basethread.py \
             pssh.spec
