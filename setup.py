#!/usr/bin/env python3

from bitsharesqt.version import VERSION, BUNDLE_NAME, SHORT_DESCRIPTION
from setuptools import setup

DATA_FILES = [ ]
APP_OPTIONS = {
#	'iconfile': 'build/app.icns',
	'excludes': [
		'PyQt4.QtDesigner', 'PyQt4.QtNetwork', 'PyQt4.QtOpenGL',
		'PyQt4.QtScript', 'PyQt4.QtSql', 'PyQt4.QtTest',
		'PyQt4.QtWebKit', 'PyQt4.QtXml', 'PyQt4.phonon',
		'PyQt4.QtMultimedia' ],
	'packages': [ 'certifi', 'cffi' ],
	'plist': {
		"CFBundleName": BUNDLE_NAME,
		"CFBundleDisplayName": SHORT_DESCRIPTION,
		"CFBundleIdentifier": "li.citadel.desktop",
		"CFBundleShortVersionString": VERSION,
	}
}

setup(
    name="citadel",
    version=VERSION,
    description=SHORT_DESCRIPTION,
    author="John Titor",
    author_email="john.titor@openmailbox.org",
    license="",
    url="https://citadel.li/desktop",
    long_description=SHORT_DESCRIPTION,
    #packages=["citadel"],
    packages=[
        "bitsharesbase",
        "bitsharesapi",
        "bitshares",
        "bitsharesextra",
        "bitsharesqt",
        "grapheneapi",
        "graphenebase",
        "websocket",
        "pytimeparse",
        "rpcs",
        "uidef",
    ],
    scripts=["citadel"],

    install_requires=[
        'six', 'ecdsa', 'appdirs',
        'qrcode', 'requests', 'pycrypto',
        'pyqtgraph'
    ],

    package_data={
        'citadel': [
           # filenames
        ]
    },

    app=['citadel'],
    data_files=DATA_FILES,
    options={'py2app': APP_OPTIONS},
    setup_requires=['py2app'],

)
