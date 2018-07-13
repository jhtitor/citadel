#!/usr/bin/env python3

from bitsharesqt.version import VERSION, BUNDLE_NAME, SHORT_DESCRIPTION
from setuptools import setup

DATA_FILES = [ ]

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
        'six', 'ecdsa', 'appdirs', 'pysocks',
        'qrcode', 'requests', 'pycryptodomex',
        'pyqtgraph', 'scrypt', 'secp256k1prp'
    ],

    package_data={
        'citadel': [
           # filenames
        ]
    },

    data_files=DATA_FILES,
    options={ },
    setup_requires=[ ],

)
