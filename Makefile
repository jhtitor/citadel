ICONSET_DIR=build/btsq.iconset
ICONSET_ICON=$(shell bitsharesqt/version.py --icon1024)
ICNS_FILE=build/app.icns
ICO_FILE=images/app.ico

SCRYPT_PATH=$(shell bitsharesqt/version.py --scryptlib)
SCRYPT_DYLIB=$(shell bitsharesqt/version.py --scryptlib --dl)
UNIX_NAME=$(shell bitsharesqt/version.py --uname)
BUNDLE_NAME=$(shell bitsharesqt/version.py --bundle)
VERSION_STRING=$(shell bitsharesqt/version.py --version)

UISRC=bitsharesqt

ui:
	mkdir -p uidef
	pyuic5 $(UISRC)/mainwindow.ui -o uidef/mainwindow.py --from-imports
	pyuic5 $(UISRC)/walletwizard.ui -o uidef/walletwizard.py --from-imports
	pyuic5 $(UISRC)/accountwizard.ui -o uidef/accountwizard.py --from-imports
	pyuic5 $(UISRC)/transactionbuilder.ui -o uidef/transactionbuilder.py --from-imports
	pyuic5 $(UISRC)/memowindow.ui -o uidef/memowindow.py --from-imports
	pyuic5 $(UISRC)/settings.ui -o uidef/settings.py --from-imports
	pyuic5 $(UISRC)/remotes.ui -o uidef/remotes.py --from-imports
	pyuic5 $(UISRC)/dashboard.ui -o uidef/dashboard.py --from-imports
	pyuic5 $(UISRC)/exchange.ui -o uidef/exchange.py --from-imports
	pyuic5 $(UISRC)/chattab.ui -o uidef/chattab.py --from-imports
	pyuic5 $(UISRC)/chatserver.ui -o uidef/chatserver.py --from-imports
	pyuic5 $(UISRC)/market.ui -o uidef/market.py --from-imports
	pyuic5 $(UISRC)/createasset.ui -o uidef/createasset.py --from-imports
	pyuic5 $(UISRC)/voting.ui -o uidef/voting.py --from-imports
	pyuic5 $(UISRC)/keyswindow.ui -o uidef/keyswindow.py --from-imports
	pyrcc5 $(UISRC)/res.qrc -o uidef/res_rc.py

sdist:
	python3 setup.py sdist

app: $(ICNS_FILE)
	rm -f version.txt
	pyinstaller -y build.spec

dmg: dist/$(BUNDLE_NAME).app
	dmgbuild -s dmg_settings.py "$(BUNDLE_NAME) $(VERSION_STRING)" dist/$(UNIX_NAME)-$(VERSION_STRING)-osx.dmg

$(ICO_FILE): $(ICONSET_ICON)
	convert -resize x32 -gravity center -crop 32x32+0+0 $(ICONSET_ICON) \
		-flatten -colors 256 $(ICO_FILE)

images/logo.png:
	cp images/bitshares_logo.png images/logo.png

clean:
	rm -rf build

clean-iconset:
	rm -R $(ICONSET_DIR)

clean-ico:
	rm $(ICO_FILE)

$(ICONSET_DIR):
	mkdir -p $(ICONSET_DIR)
	sips -z 16 16     $(ICONSET_ICON) --out $(ICONSET_DIR)/icon_16x16.png
	sips -z 32 32     $(ICONSET_ICON) --out $(ICONSET_DIR)/icon_16x16@2x.png
	sips -z 32 32     $(ICONSET_ICON) --out $(ICONSET_DIR)/icon_32x32.png
	sips -z 64 64     $(ICONSET_ICON) --out $(ICONSET_DIR)/icon_32x32@2x.png
	sips -z 128 128   $(ICONSET_ICON) --out $(ICONSET_DIR)/icon_128x128.png
	sips -z 256 256   $(ICONSET_ICON) --out $(ICONSET_DIR)/icon_128x128@2x.png
	sips -z 256 256   $(ICONSET_ICON) --out $(ICONSET_DIR)/icon_256x256.png
	sips -z 512 512   $(ICONSET_ICON) --out $(ICONSET_DIR)/icon_256x256@2x.png
	sips -z 512 512   $(ICONSET_ICON) --out $(ICONSET_DIR)/icon_512x512.png
	cp                $(ICONSET_ICON)       $(ICONSET_DIR)/icon_512x512@2x.png

$(ICNS_FILE): $(ICONSET_DIR)
	iconutil -c icns $(ICONSET_DIR) --output $(ICNS_FILE)

icns: $(ICNS_FILE)
	echo "OK"