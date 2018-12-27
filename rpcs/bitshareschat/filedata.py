import os
from io import BytesIO

try:
	import magic
#	from magic.api import MagicError
	HAS_MAGIC = True
except ImportError:
	import mimetypes
	HAS_MAGIC = False
	print("filemagic not found")

try:
	from PILLOW import Image
	HAS_PIL = "PILLOW"
except ImportError:
	try:
		from PIL import Image
		HAS_PIL = "PIL"
	except:
		HAS_PIL = False
		print("PIL or PILLOW not found")

import sys
def resource_path(relative_path):
	""" Get absolute path to resource, works for dev and for PyInstaller """
	try:
		# PyInstaller creates a temp folder and stores path in _MEIPASS
		base_path = sys._MEIPASS
	except Exception:
		base_path = os.path.abspath(".")
	return os.path.join(base_path, relative_path)

def is_bundled():
	try:
		str(sys._MEIPASS)
		return True
	except Exception:
		return False


# return best file info we can
def fileinfo(path):
	basename = os.path.basename(path)
	stats = os.stat(path)
	mimetype = guess_mime(path)
	return {
		"filename": basename,
		"content-type": mimetype,
		"content-length": stats.st_size,
	}



def guess_mime(path):
	if HAS_MAGIC:
		paths = [ resource_path("magic.mgc") ] if is_bundled() else None
#		try:
		with magic.Magic(paths=paths, flags=magic.MAGIC_MIME_TYPE) as m:
			content_type = m.id_filename(path)
#		except MagicError:
#			HAS_MAGIC = False
#			return guess_mime(path)
	else:
		content_type = mimetypes.guess_type(path)[0]
	return content_type



import hashlib
def sha256(s):
	return hashlib.sha256(s.encode('ascii')).hexdigest()
def sha512(s):
	return hashlib.sha512(s.encode('ascii')).hexdigest()


def fileToThumbnail(filename):
	if not HAS_PIL: return ""
	img = Image.open(filename)
	img.thumbnail((200, 200))
	buf = BytesIO()
	img.save(buf, format="PNG")
	
	content_type = Image.MIME[img.format]
	
	# FIXME: stream encoding
	data = buf.getvalue()
	encoded = b64encode(data)
	size = len(data)
	# FIXME: stream this too
	return "data:" + content_type + ";base64," + encoded.decode('ascii'), content_type, size

import json
def parseMessage(s, try_json=True):
	j = None
	b, ct = None, None
	if try_json:
		try:
			j = json.loads(s)
			ct = "application/json"
		except:
			pass
	if j and "message" in j:
		j["message"] = parseMessage(j["message"], try_json=False)
	if j and "content-type" in j:
		ct = j["content-type"]
	if j:
		return j, ct
	try:
		b, ct = parseDataURI(s)
		return b, ct
	except:
		pass
	# return as is
	return s, "text/plain"

from base64 import b64decode, b64encode
def parseDataURI(data_uri):
	if not data_uri.startswith("data:"):
		raise ValueError("Must start with `data:`")
	header, encoded = data_uri.split(",", 1)
	parts = header.split(";")
	ct = parts[0][len("data:"):]
	enc = parts[-1]
	if enc != "base64":
		raise ValueError("Encoding must be base64")
	return b64decode(encoded), ct

def fileToDataURI(filename, content_type="application/octet-stream"):
	content_type = guess_mime(filename)
	with open(filename, 'rb') as f:
		data = f.read()
	#	with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
	#		content_type = m.id_buffer(data)
	# TODO: use streams
	encoded = b64encode(data)
	size = len(data)
	return "data:" + content_type + ";base64," + encoded.decode('ascii'), content_type, size
