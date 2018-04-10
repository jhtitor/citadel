#!/usr/bin/env python3

VERSION="0.1.0"

BUNDLE_NAME="BitShares-QT"
UNIX_NAME="pybitshares-qt"
LOGO_1024="images/bitshares_1024x1024.png"
SHORT_DESCRIPTION="BitShares Wallet"

BUNDLE_NAME="Citadel"
UNIX_NAME="citadel"
LOGO_1024="images/citadel_1024x1024.png"
SHORT_DESCRIPTION="Citadel BitShares Wallet"

if __name__ == "__main__":
	import sys
	def out(s):
		sys.stdout.write(s)
		sys.stdout.flush()
		sys.exit(0)
	if ("--logo1024" in sys.argv):
		out(LOGO_1024)
	if ("--icon1024" in sys.argv):
		out(LOGO_1024)
	if ("--bundle" in sys.argv):
		out(BUNDLE_NAME)
	if ("--uname" in sys.argv):
		out(UNIX_NAME)
	if ("--short" in sys.argv):
		VERSION = VERSION.replace(".","")
	if ("--scryptlib" in sys.argv):
		import imp
		so = imp.find_module('_scrypt')[1]
		if ("--dl" in sys.argv):
			import subprocess
			lines = subprocess.run(["otool", "-L", so], stdout=subprocess.PIPE).stdout.decode('utf8')
			lines = str.split(lines, "\n")
			dylib = str.split(lines[1], " (")[0].strip()
			out(dylib)
		out(so)
	out(VERSION)
