INSTALL_CMD = install

FILES = \
	dbus_characterdisplay.py \
	cache.py \
	lcddriver.py \
	track.py \
	pages.py \
	four_button_pages.py \
	four_button_ui.py \
	simple_ui.py \
	payg_service.py

compile: ;

help:
	@echo "The following make targets are available"
	@echo " help - print this message"
	@echo " install - install everything"
	@echo " clean - remove temporary files"

install_app : $(FILES)
	@if [ "$^" != "" ]; then \
		$(INSTALL_CMD) -d $(DESTDIR)$(bindir); \
		$(INSTALL_CMD) -t $(DESTDIR)$(bindir) $^; \
		echo installed $(DESTDIR)$(bindir)/$(notdir $^); \
	fi

clean distclean: ;

install: install_app

testinstall:
	$(eval TMP := $(shell mktemp -d))
	$(MAKE) DESTDIR=$(TMP) install
	(cd $(TMP) && ./dbus_characterdisplay.py --help > /dev/null)
	-rm -rf $(TMP)

%.mo: %.po
	msgfmt -o $@ $<

lang/messages.pot:
	pygettext --output-dir=lang pages.py

.PHONY: help install_app install clean distclean testinstall
