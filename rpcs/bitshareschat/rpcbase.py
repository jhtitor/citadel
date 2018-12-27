import requests
import requests.exceptions
import datetime

AD_HEADER = "X-BitShares2-Chat-HTTP-Endpoint"
AD_HEADER_WS = "X-BitShares2-Chat-WS-Endpoint"

from bitsharesbase import memo as BTSMemo
from bitsharesbase.account import PrivateKey
from bitsharesbase.account import PublicKey

from graphenebase.account import PrivateKey as GPHPrivateKey
from graphenebase.account import PublicKey as GPHPublicKey

import hashlib
from bitsharesbase.objects import Memo as WireMemo # for hashing

from .filedata import *

class ChatRPCException(Exception):
	pass

class TokenExpired(ChatRPCException):
	def __init__(self, token, *args, **kwargs):
		super(TokenExpired, self).__init__(*args, **kwargs)
		self.token = token

class MissingKey(ChatRPCException):
	pass

class UnspecifiedKey(ChatRPCException):
	""" An RPC method was called without a source public key.
	    The RPC instance has more that one private key attached,
	    making it impossible to guess which one to use.
	
	    Either only attach single private key, either
	    call all methods with "pubkey" argument, specifying one.
	"""
	pass

class APIError(ChatRPCException):
	def __init__(self, *args, code=500, **kwargs):
		super(APIError,self).__init__(*args,**kwargs)
		self.code = code

class DiscoveryFailed(ChatRPCException):
	pass

class ConnectionError(ChatRPCException, requests.exceptions.ConnectionError):
	pass


class BitSharesChatRPC():
	def __init__(self, privkey, server, autodiscover=True, autorefresh=True):
		self.url = server
		self.discovered = not(autodiscover)
		if not isinstance(privkey, (PrivateKey, GPHPrivateKey)):
			privkey = PrivateKey(privkey)
		self.privkeys = {
			str(privkey.pubkey): privkey
		}
		self.autorefresh = autorefresh
		self.config = None
		self.headers = {
			'Accept': 'application/json', 'Content-Type': 'application/json',
			'User-Agent': "python-bitshareschat"
		}
		self.last_msg_id = { } # per pubkey
		self.room_keys = [ ]


	# Auto-discovery
	
	@classmethod
	def discover(self, url, proxyUrl=None):
		""" Returns (HTTP, WS) endpoints tuple """
		from ._websocket import BitSharesChatWS
		from ._http import BitSharesChatHTTP

		otk = PrivateKey()

		# Try websockets
		if url.startswith("ws://") or url.startswith("wss://"):
			ws = BitSharesChatWS(otk, url, proxyUrl=proxyUrl)
			try:
				s = ws.make_request("status", { })
				w_url = url
				h_url = s["http_endpoints"][0]
				return (h_url, w_url)
			except ConnectionError:
				raise
			except:
				import traceback
				traceback.print_exc()
				pass # continue
			finally:
				ws.stop()
		url = url.replace("ws://", "http://")
		url = url.replace("wss://", "https://")

		# Try HTTP connection
		http = BitSharesChatHTTP(otk, url, proxyUrl=proxyUrl)
		try:
			s = http.make_request("status", { }, autodiscover=False)
			h_url = url
			w_url = s["websocket_endpoints"][0]
			return (h_url, w_url)
		except ConnectionError:
			raise
		except:
			import traceback
			traceback.print_exc()
			pass # continue
		
		# Try web-discovery
		h_url, w_url = http.web_discover(url)
		return (h_url, w_url)
	
	def web_discover(self, url):
		raise NotImplemented
	
	
	# CRYPTO
	def guessKey(self, pubkey=None):
		if pubkey is None:
			if len(self.privkeys) > 1:
				raise UnspecifiedKey("Trying to guess a key from several possible.")
			pubkey = str(list(self.privkeys.keys())[0])
		return pubkey
	
	def encodeMemo(self, from_pubkey, to_pubkey, clear_text):
		from_pubkey = self.guessKey(from_pubkey)
		privkey = self.privkeys[str(from_pubkey)]
		if not isinstance(from_pubkey, (PublicKey, GPHPublicKey)):
			from_pubkey = PublicKey(from_pubkey, prefix=from_pubkey[0:3])
		if not isinstance(to_pubkey, (PublicKey, GPHPublicKey)):
			to_pubkey = PublicKey(to_pubkey, prefix=to_pubkey[0:3])
		import random
		nonce = str(random.getrandbits(64))
		cipher = BTSMemo.encode_memo(
			privkey,
			to_pubkey,
			nonce,
			clear_text
		)
		return { "to": str(to_pubkey),
			"from": str(privkey.pubkey),
			"nonce": nonce,
			"message": cipher }

	def decodeMemo(self, **kwargs):
		from_pubkey = kwargs.get('from')
		to_pubkey = kwargs.get('to')
		nonce = kwargs.get('nonce')
		cipher_text = kwargs.get('message')
#		local_privkey = self.privkeys[0]
		if not isinstance(from_pubkey, PublicKey):
			from_pubkey = PublicKey(from_pubkey, prefix=from_pubkey[0:3])
		if not isinstance(to_pubkey, PublicKey):
			to_pubkey = PublicKey(to_pubkey, prefix=to_pubkey[0:3])
#		if str(self.pubkey) == str(from_pubkey):
#			other_pubkey = to_pubkey
#		elif str(self.pubkey) == str(to_pubkey):
#			other_pubkey = from_pubkey
		if str(from_pubkey) in self.privkeys:
			local_privkey = self.privkeys[str(from_pubkey)]
			other_pubkey = to_pubkey
		elif str(to_pubkey) in self.privkeys:
			local_privkey = self.privkeys[str(to_pubkey)]
			other_pubkey = from_pubkey
		else:
			raise MissingKey("No Private Key found for neither %s nor %s public keys" % (str(from_pubkey), str(to_pubkey)))
		clear = BTSMemo.decode_memo(
			local_privkey,
			other_pubkey,
			nonce,
			cipher_text
		)
		return clear
	
	# HELPER METHODS
	def subscribe(self, priv_key):
		self.privkeys[str(priv_key.pubkey)] = priv_key
	
	def getMessages(self, pubkeys=None, decode=True):
		if pubkeys is None:
			pubkeys = list(self.privkeys.keys())
		for pubkey in pubkeys:
			while True:
				msgs = self.get_messages(
					start=self.last_msg_id.get(str(pubkey),""),
					pubkey=str(pubkey)
				)
				if len(msgs) < 1: break
				for msg in msgs:
					memo = msg["memo"]
					if decode and memo["message"]:
						try:
							data = self.decodeMemo(**memo)
							msg["message"] = data
						except:
							pass
					meta = msg["meta"]
					if decode and meta:
						try:
							meta['from'] = memo['from']
							meta['to'] = memo['to']
							data = self.decodeMemo(**meta)
							msg["meta_data"] = data
						except:
							pass
					yield msg
					self.last_msg_id[pubkey] = msg['id']

	def verifyMessages(self, ids, pubkey=None):
		seq, size = ids, 100
		sub_lists = [seq[i:i+size] for i in range(0, len(seq), size)]
		for sub_list in sub_lists:
			r = self.verify_messages(sub_list,pubkey=pubkey)
			#print("?", r, "[", len(ids), "]")
			for res in r:
				yield res

	def sendMemo(self, memo):
		return self.post_memo(memo)

	def sendMessage(self, to_pubkey, clear_text, from_pubkey=None):
		return self.sendMemo( self.encodeMemo(from_pubkey, to_pubkey, clear_text) )

	def sendInlineFile(self, to_pubkey, filename, from_pubkey=None):
		clearbody, ct, size = fileToDataURI(filename)
		memoF = self.encodeMemo(from_pubkey, to_pubkey, clearbody)
		return self.sendMemo(memoF)

	def sendFile(self, to_pubkey, filename, from_pubkey=None):
		import os
		basename = os.path.basename(filename)
		clearbody, ct, size = fileToDataURI(filename)
		try:
			thumbnail, _ , _  = fileToThumbnail(filename)
		except:
			thumbnail = None
		import json
		info = { "content-type": ct,
			"content-length": size,
			"thumbnail": thumbnail,
			"filename": basename }
		memoI = self.encodeMemo(from_pubkey, to_pubkey, json.dumps(info))
		memoF = self.encodeMemo(from_pubkey, to_pubkey, clearbody)
		
		return self.post_filememo(memoF, memoI)


	def saveFile(self, filemsgid, filename, pub_from=None, pub_to=None, nonce=None):
		if pub_from is None or nonce is None or pub_to is None:
			memo = self.get_message_headers(filemsgid)
			pub_from = memo["from"]
			pub_to = memo["to"]
			nonce = memo["nonce"]
		encbody = self.download_message(filemsgid)
		#print("Downloaded", len(encbody), "bytes")
		clearbody = self.decodeMemo(**{
			"to": pub_to,
			"from": pub_from,
			"nonce": nonce,
			"message": encbody.decode()})
		b, ct = parseDataURI(clearbody)
		with open(filename, "wb") as f:
			f.write(b)

	def acceptFile(self, msg, filename=None):
		if not filename:
			meta, _ = parseMessage(msg["meta_data"])
			filename = meta["filename"]
		
		self.saveFile(msg["id"], filename, msg["memo"]["from"], msg["memo"]["to"], msg["memo"]["nonce"])

	def acceptThumbnail(self, msg, filename):
		meta, _ = parseMessage(msg["meta_data"])
		clearbody = meta["thumbnail"]
		b, ct = parseDataURI(clearbody)
		with open(filename, "wb") as f:
			f.write(b)

	def hashMessage(self, memo):
		wm = WireMemo(memo) # proper field order
		wmb = bytes(wm)     # proper conversion
		return hashlib.sha256(wmb).hexdigest()
