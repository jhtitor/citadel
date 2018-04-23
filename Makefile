ICONSET_DIR=build/btsq.iconset
ICONSET_ICON=$(shell bitsharesqt/version.py --icon1024)
ICNS_FILE=build/app.icns
ICO_FILE=images/app.ico

SCRYPT_PATH=$(shell bitsharesqt/version.py --scryptlib)
SCRYPT_DYLIB=$(shell bitsharesqt/version.py --scryptlib --dl)
BUNDLE_NAME=$(shell bitsharesqt/version.py --bundle)

UISRC=bitsharesqt

ui:
	mkdir -p uidef
	pyuic4 $(UISRC)/mainwindow.ui -o uidef/mainwindow.py --from-imports
	pyuic4 $(UISRC)/accountwizard.ui -o uidef/accountwizard.py --from-imports
	pyuic4 $(UISRC)/transactionbuilder.ui -o uidef/transactionbuilder.py --from-imports
	pyuic4 $(UISRC)/memowindow.ui -o uidef/memowindow.py --from-imports
	pyuic4 $(UISRC)/settings.ui -o uidef/settings.py --from-imports
	pyuic4 $(UISRC)/remotes.ui -o uidef/remotes.py --from-imports
	pyuic4 $(UISRC)/dashboard.ui -o uidef/dashboard.py --from-imports
	pyuic4 $(UISRC)/exchange.ui -o uidef/exchange.py --from-imports
	pyuic4 $(UISRC)/market.ui -o uidef/market.py --from-imports
	pyuic4 $(UISRC)/createasset.ui -o uidef/createasset.py --from-imports
	pyrcc4 -py3 $(UISRC)/res.qrc -o uidef/res_rc.py

App: $(ICNS_FILE)
	python3 setup.py py2app --iconfile $(ICNS_FILE)
	cp $(SCRYPT_PATH) dist/$(BUNDLE_NAME).app/Contents/Resources/lib/python3.5/lib-dynload/_scrypt.so
	install_name_tool -change $(SCRYPT_DYLIB) @executable_path/../Frameworks/libcrypto.1.0.0.dylib dist/$(BUNDLE_NAME).app/Contents/Resources/lib/python3.5/lib-dynload/_scrypt.so

win32: $(ICO_FILE)
	pyinstaller -D --windowed --icon $(ICO_FILE) citadel

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