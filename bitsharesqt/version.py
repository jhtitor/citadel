#!/usr/bin/env python3

VERSION="0.2.5"

BUNDLE_NAME="BitShares-QT"
UNIX_NAME="pybitshares-qt"
LOGO_1024="images/bitshares_1024x1024.png"
SHORT_DESCRIPTION="BitShares Wallet"

BUNDLE_NAME="Citadel"
UNIX_NAME="citadel"
LOGO_1024="images/citadel_1024x1024.png"
SHORT_DESCRIPTION="Citadel BitShares Wallet"

import os
import sys
def resource_path(relative_path):
	""" Get absolute path to resource, works for dev and for PyInstaller """
	try:
		# PyInstaller creates a temp folder and stores path in _MEIPASS
		base_path = sys._MEIPASS
	except Exception:
		base_path = os.path.abspath(".")
	return os.path.join(base_path, relative_path)

def txt_version(on_error="Unknown"):
	try:
		path = resource_path("version.txt")
		with open(path) as f:
			return f.read().strip()
	except:
		return on_error

# Return the git revision as a string (stolen from numpy)
def git_version(on_error="Unknown"):
	import os, subprocess
	def _minimal_ext_cmd(cmd):
		env = { } # construct minimal environment
		for k in ['SYSTEMROOT', 'PATH']:
			v = os.environ.get(k)
			if v is not None: env[k] = v
		# LANGUAGE is used on win32
		env['LANGUAGE'] = env['LANG'] = env['LC_ALL'] = 'C'
		return subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env).communicate()[0].strip().decode('ascii')
	try:
		GIT_BRANCH = _minimal_ext_cmd(['git', 'rev-parse' ,'--abbrev-ref', 'HEAD'])
		if not(GIT_BRANCH): return on_error
		if GIT_BRANCH == "master": return on_error
		#GIT_REVISION   = _minimal_ext_cmd(['git', 'rev-parse', 'HEAD'])
		GIT_REVISION = _minimal_ext_cmd(['git', 'describe', '--always'])
	except OSError:
		GIT_REVISION = on_error
	return GIT_REVISION

VERSION=git_version(VERSION)
VERSION=txt_version(VERSION)

def platform_string():
	import platform
	base = platform.system() + " " + platform.release()
	if platform.system() == 'Darwin':
		osx = platform.mac_ver()[0]
		if osx:
			base = "Mac OS X " + osx
	return base + " " + platform.machine()

def library_versions(platform=False):
	info = ""
	from PyQt5.QtCore import QT_VERSION_STR
	from PyQt5.Qt import PYQT_VERSION_STR
	from sip import SIP_VERSION_STR
	import sys
	if platform:
	    info += "platform: " + platform_string() + "\n\n"
	info += "python " + sys.version + "\n"
	info += "QT " + QT_VERSION_STR + "\n"
	info += "SIP " + SIP_VERSION_STR + "\n"
	info += "PyQt " + PYQT_VERSION_STR + "\n"
	return info

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
	if ("--platform" in sys.argv):
		out(platform_string())
	if ("--libraries" in sys.argv):
		out(library_versions())
	out(VERSION)
