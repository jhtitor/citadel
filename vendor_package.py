#!/usr/bin/env python3

import os
import os.path
import shutil
import tarfile
try:
    from urllib2 import urlopen, URLError
except ImportError:
    from urllib.request import urlopen
    from urllib.error import URLError
from io import BytesIO

TMP_DIR="build/vendor"

def github_url(repo, commit, format="tar.gz"):
	return "https://github.com/%s/archive/%s.%s" % (repo, commit, format)

packages = [
	{
		"name": "python-bitshares",
		"repo": (
			"jhtitor/python-bitshares",
			"705db25a47e9e3fffd28aa68aa518bbc47c2798c"
			),
		"copy": [ "bitsharesbase", "bitsharesapi", "bitshares" ],
	},
	{
		"name": "python-graphenelib",
		"repo": (
			"jhtitor/python-graphenelib",
			"6437c84aac1c9d003896e87c9ae06d9031b25a93"
			),
		"copy": [ "graphenebase", "grapheneapi", "graphenestorage" ],
	},
	{
		"name": "websocket",
		"repo": ("jhtitor/websocket-client", "master"),
		"copy": [ "websocket" ],
	},
	{
		"name": "pytimeparse",
		"repo": ("jhtitor/pytimeparse", "master"),
		"copy": [ "pytimeparse" ],
	},
]

def file_exists(path):
	return os.path.exists(path)

def download_archive(package):
	url = github_url(*package['repo'])
	libdir = os.path.join(TMP_DIR, package["name"])
	
	if os.path.exists(os.path.join(libdir, "setup.py")):
		return
	print("* %s : downloading %s" % (package["name"], url))
	
	try:
		r = urlopen(url)
		if r.getcode() == 200:
			content = BytesIO(r.read())
			content.seek(0)
			with tarfile.open(fileobj=content) as tf:
				dirname = tf.getnames()[0].partition('/')[0]
				tf.extractall(TMP_DIR)
			shutil.move(os.path.join(TMP_DIR, dirname), libdir)
		else:
			raise Exception("HTTP ERROR %d" % (r.getcode()))
	except URLError as ex:
		#print(ex.message)
		raise ex

for package in packages:
	libdir = os.path.join(TMP_DIR, package["name"])
	for op in package["copy"]:
		sdir = os.path.join(libdir, op)
		tdir = os.path.join('.', op)
		if file_exists(tdir):
			print("* %s : already in place" % (op))
			continue
		if not(file_exists(sdir)):
			download_archive(package)
		
		shutil.copytree(sdir, tdir)
		print("* %s : copied %s -> %s" % (op, sdir, tdir))
