PREFIX  ?= /usr
DESTDIR ?=

APP_ID      := net.tecktron.md_viewer
PYTHON_DIST := $(DESTDIR)$(PREFIX)/lib/python3/dist-packages
ICON_SIZES  := 16x16 22x22 24x24 32x32 48x48 64x64 128x128 256x256

.PHONY: install uninstall

install:
	# Python package
	install -d $(PYTHON_DIST)/md_viewer
	cp -r src/md_viewer/. $(PYTHON_DIST)/md_viewer/
	find $(PYTHON_DIST)/md_viewer -name '__pycache__' -exec rm -rf {} + 2>/dev/null; true

	# Entry point
	install -d $(DESTDIR)$(PREFIX)/bin
	install -m 755 bin/md-viewer $(DESTDIR)$(PREFIX)/bin/md-viewer

	# Manual page
	install -d $(DESTDIR)$(PREFIX)/share/man/man1
	install -m 644 data/md-viewer.1 $(DESTDIR)$(PREFIX)/share/man/man1/

	# Desktop integration
	install -d $(DESTDIR)$(PREFIX)/share/applications
	install -m 644 data/$(APP_ID).desktop $(DESTDIR)$(PREFIX)/share/applications/
	for size in $(ICON_SIZES); do \
		install -d $(DESTDIR)$(PREFIX)/share/icons/hicolor/$$size/apps; \
		install -m 644 data/icons/hicolor/$$size/apps/$(APP_ID).png \
			$(DESTDIR)$(PREFIX)/share/icons/hicolor/$$size/apps/; \
	done
	install -d $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps
	install -m 644 data/icons/hicolor/scalable/apps/$(APP_ID).svg \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/

	# Built-in styles
	install -d $(DESTDIR)$(PREFIX)/share/xfce-md-viewer/styles
	install -m 644 data/styles/*.css $(DESTDIR)$(PREFIX)/share/xfce-md-viewer/styles/

	# Page scripts (ours) and vendored KaTeX / Mermaid
	cp -r data/js data/vendor $(DESTDIR)$(PREFIX)/share/xfce-md-viewer/
	find $(DESTDIR)$(PREFIX)/share/xfce-md-viewer/js $(DESTDIR)$(PREFIX)/share/xfce-md-viewer/vendor \
		-type d -exec chmod 755 {} + -o -type f -exec chmod 644 {} +

	# GSettings schema
	install -d $(DESTDIR)$(PREFIX)/share/glib-2.0/schemas
	install -m 644 data/$(APP_ID).gschema.xml $(DESTDIR)$(PREFIX)/share/glib-2.0/schemas/

	# AppStream metadata
	install -d $(DESTDIR)$(PREFIX)/share/metainfo
	install -m 644 data/$(APP_ID).metainfo.xml $(DESTDIR)$(PREFIX)/share/metainfo/

	# Post-install hooks (skipped when DESTDIR is set — package build handles these)
ifeq ($(DESTDIR),)
	glib-compile-schemas $(PREFIX)/share/glib-2.0/schemas/
	gtk-update-icon-cache -f -t $(PREFIX)/share/icons/hicolor
	update-desktop-database $(PREFIX)/share/applications 2>/dev/null || true
endif

uninstall:
	rm -rf $(PYTHON_DIST)/md_viewer/
	rm -f  $(DESTDIR)$(PREFIX)/bin/md-viewer
	rm -f  $(DESTDIR)$(PREFIX)/share/man/man1/md-viewer.1
	rm -f  $(DESTDIR)$(PREFIX)/share/applications/$(APP_ID).desktop
	for size in $(ICON_SIZES); do \
		rm -f $(DESTDIR)$(PREFIX)/share/icons/hicolor/$$size/apps/$(APP_ID).png; \
	done
	rm -f  $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/$(APP_ID).svg
	rm -rf $(DESTDIR)$(PREFIX)/share/xfce-md-viewer/
	rm -f  $(DESTDIR)$(PREFIX)/share/glib-2.0/schemas/$(APP_ID).gschema.xml
	rm -f  $(DESTDIR)$(PREFIX)/share/metainfo/$(APP_ID).metainfo.xml
ifeq ($(DESTDIR),)
	glib-compile-schemas $(PREFIX)/share/glib-2.0/schemas/
	gtk-update-icon-cache -f -t $(PREFIX)/share/icons/hicolor
	update-desktop-database $(PREFIX)/share/applications 2>/dev/null || true
endif
