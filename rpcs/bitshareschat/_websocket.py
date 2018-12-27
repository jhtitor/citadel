import datetime
import threading
import queue
import json
import time

import ssl
import socket
import websocket

from .rpcbase import BitSharesChatRPC
from .rpcbase import(
	ChatRPCException,
	TokenExpired,
	APIError,
	DiscoveryFailed,
	ConnectionError,
)

import urllib # for proxy parser

class MutexSet(set):
	def __init__(self, *args, **kwargs):
		super(MutexSet).__init__(*args, **kwargs)
		self.lock = threading.Lock()

	def __len__(self):
		with self.lock:
			return super(MutexSet, self).__len__()

	def __getitem__(self, key):
		with self.lock:
			return super(MutexSet, self).__getitem__(key)

	def __contains__(self, val):
		with self.lock:
			return super(MutexSet, self).__contains__(val)

	def __iter__(self, *args, **kwargs):
		with self.lock:
			return super(MutexSet, self).__iter__(*args, **kwargs)

	def add(self, val):
		sin = super(MutexSet, self).__contains__
		with self.lock:
			if sin(val):
				return False
			return super(MutexSet, self).add(val)

	def remove(self, val, *args, **kwargs):
		sin = super(MutexSet, self).__contains__
		with self.lock:
			if not sin(val):
				return False
			return super(MutexSet, self).remove(val)


class MutexDict(dict):
	def __init__(self, *args, **kwargs):
		super(MutexDict).__init__(*args, **kwargs)
		self.lock = threading.Lock()

	def __len__(self):
		with self.lock:
			return super(MutexDict, self).__len__()

	def __getitem__(self, key):
		with self.lock:
			return super(MutexDict, self).__getitem__(key)

	def __setitem__(self, key, val):
		with self.lock:
			return super(MutexDict, self).__setitem__(key, val)

	def get(self, key, *args, **kwargs):
		with self.lock:
			return super(MutexDict, self).get(key, *args, **kwargs)

	def pop(self, key, *args, **kwargs):
		with self.lock:
			return super(MutexDict, self).pop(key, *args, **kwargs)


class BitSharesChatWS(BitSharesChatRPC):

	def __init__(self, *args,
			on_update = None,
			on_connect = None,
			on_disconnect = None,
			proxyUrl=None, **kwargs):

		super(BitSharesChatWS, self).__init__(*args, **kwargs)
		sopt = ((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),)
		
		self.authed_keys = MutexSet()
		
		self.proxyUrl = proxyUrl
		
		self.request_id = 0
		self.request_id_lock = threading.Lock()
		self.refreshing_token = False
		self.requests = queue.Queue()
		self.replies = MutexDict()
		self.updates = queue.Queue()
		self.on_update = on_update
		self.on_connect = on_connect
		self.on_disconnect = on_disconnect
		self.connected = Ellipsis
		self.teardown = False
		self.calmness = 0
		self.connection_id = 0
		self.stopped = True
		
		self.start()

	def start(self):
		if not self.stopped: return
		self.stopped = False
		self.teardown = False
		self.thread = threading.Thread(target=self.__forever, args=( ))
		self.thread.start()

	def stop(self):
		self.teardown = True
		self.refreshing_token = False
		try:
			self.ws.close()
		except:
			pass

	def __del__(self):
		self.stop()

	def __forever(self):
		while not self.teardown:
			self.run_once()
			self.connection_id += 1
			with self.request_id_lock:
				self.request_id = 0
			self.authed_keys = MutexSet()
		self.stopped = True

	def parseProxyUrl(self, proxy_url):
		d = { }
		if not proxy_url:
			return d
		try:
			url = urllib.parse.urlparse(proxy_url)
			d['http_proxy_host'] = url.hostname
			d['http_proxy_port'] = url.port
			d['proxy_type'] = url.scheme.lower()
			if url.username or url.password:
				d['http_proxy_auth'] = (url.username, url.password)
		except Exception as e:
			raise ValueError("Can not parse proxy URL %s -- %s" % (proxy_url, str(e)))
		return d

	def run_once(self):
		proxy_kwargs = self.parseProxyUrl(self.proxyUrl)
		self.ws = websocket.WebSocketApp(
			self.url,
			on_message=self.on_message,
			on_error=self.on_error,
			on_close=self.on_close,
			on_open=self.on_open,
		)
		if self.url.startswith("wss://"):
			proxy_kwargs["sslopt"] = {'cert_reqs': ssl.CERT_NONE}
		self.ws.run_forever(**proxy_kwargs)
		self.calmness = min(self.calmness+1, 60)
		for i in range(self.calmness * 10):
			if not(self.teardown):
				time.sleep(0.1)

	def queue_send(self, payload):
		if not(self.connected is True):
			self.requests.put(payload, block=True)
			return
		try:
			self.ws.send(json.dumps(payload, ensure_ascii=False).encode('utf8'))
		except Exception as e:
			self.on_error(self.ws, e)

	def flush_send(self):
		while True:
			try:
				payload = self.requests.get(block=False)
			except:
				payload = None
			if not payload:
				break
#			print(id(self), "sending req", "{", payload["id"],"}")
			self.ws.send(json.dumps(payload, ensure_ascii=False).encode('utf8'))

	def on_open(self, ws):
		self.connected = True
		self.flush_send()
		if self.on_connect:
			self.on_connect(self)
#		self.refresh_token()
		self.calmness = 0 # become eager again

	def on_error(self, ws, err):
#		print("WS ERROR ", str(err))
		self.connected = False
		if self.on_disconnect:
			self.on_disconnect(self)

	def on_close(self, ws):
		was = self.connected
		self.connected = False
		if was and self.on_disconnect:
			self.on_disconnect(self)

	def on_message(self, ws, frame):
		pkt = json.loads(frame)
		if "update" in pkt:
			if self.on_update:
				self.on_update(pkt, self)
			else:
				self.updates.put(pkt, block=False)
			return
		self.replies[pkt["id"]] = pkt

	def get_updates(self):
		while True:
			b = self.updates.get(block=False)
			if not b: break
			yield b

	def get_request_id(self):
		with self.request_id_lock:
			self.request_id += 1
			return self.request_id

	def queue_request(self, method, data):
		query = {
			"jsonrpc": "2.0",
			"id": self.get_request_id(),
			"method": method,
			"params": data,
		}
		#print("*", method, data)
		self.queue_send(query)
		return query["id"]

	def make_request(self, *args, blocking=True, **kwargs):
		timeout = 15
		c_id = None
		r_id = None
		while True:
#			print(id(self), "... ", args[0], "{",r_id,"}", timeout, len(self.replies), id(self.replies))
			if timeout <= 0:
				break
			if self.connection_id != c_id:
				c_id = self.connection_id
				r_id = self.queue_request(*args, **kwargs)
			if self.connected is False:
#				print("No connection")
				break
			resp = self.replies.pop(r_id, None)
			if resp:
				if 'error' in resp:
					raise APIError(resp['error']['message'], code=resp['error']['code'])
#				from pprint import pprint
#				print(id(self), " for ", "{",r_id,"}")
#				pprint(resp)
				return resp['result']
			time.sleep(0.1)
			timeout -= 0.1
		raise ConnectionError("No reply (was calling %s)" % args[0])

	def autoDiscover(self, url):
		if self.discovered: return
		h, w = self.__class__.discover(url, self.proxies['http'] if self.proxies else None)
		self.url = h
		self.discovered = True

	# Token Management
	
	def refresh_token(self, pubkey):
		pubkey = self.guessKey(pubkey)
		if not len(self.authed_keys):
			s = self.status()
			for p in s["pubkeys"]:
				self.authed_keys.add(p)
		timeout = 5
		while self.refreshing_token:
			if timeout <= 0:
				break
			timeout -= 0.1
			time.sleep(0.1)
		if str(pubkey) in self.authed_keys:
			return pubkey

		self.refreshing_token = True
		try:
			chal = self.get_challenge(str(pubkey))
			memo = chal['challenge']
			cleartext = self.decodeMemo(**memo)
			key = self.respond_challenge(chal['key'], cleartext)
			self.authed_keys.add(key)
		finally:
			self.refreshing_token = False
		return key
	
#	def subscribe(self, pubkey=None):
#		self.refresh_token(pubkey)

	# LOGIN METHODS
	
	def get_challenge(self, pubkey):
		return self.make_request('get_challenge', {
			"pubkey": str(pubkey)
		})
	
	def respond_challenge(self, authkey, response):
		return self.make_request('respond_challenge', {
			"key": authkey,
			"response": response
		})
	
	def status(self):
		return self.make_request('status', [ ])

	def motd(self):
		return self.make_request('motd', [ ])

	# MAIN METHODS
	
	def autoretry(func):
		return func

	@autoretry
	def get_messages(self, start="", limit=100, to="", from_="", either="", pubkey=None):
		if not pubkey and from_ and from_ in self.authed_keys:
			pubkey = self.refresh_token(from_)
		elif not pubkey and to and to in self.authed_keys:
			pubkey = self.refresh_token(to)
		else:
			pubkey = self.refresh_token(pubkey)
		return self.make_request('get_messages', {
			"start": start,
			"limit": limit,
			"to": to,
			"from": from_,
			"either": either,
			"token": str(pubkey),
		})

	@autoretry
	def post_memo(self, memo):
		""" Send previously prapared memo object. """
		self.refresh_token(memo["from"])
		return self.make_request('post_message', {
			"memo": memo
		})

	@autoretry
	def post_message(self, to_pubkey, clear_text, from_pubkey=None):
		""" Prepare new memo object and send it. """
		self.refresh_token(from_pubkey)
		return self.make_request('post_message', {
			"memo": self.encodeMemo(to_pubkey, clear_text)
		})

	@autoretry
	def post_filememo(self, filememo, metamemo, pubkey=None):
		raise NotImplemented

	@autoretry
	def verify_messages(self, ids, pubkey=None):
		pubkey = self.refresh_token(pubkey)
		return self.make_request('verify_messages', {
			"pubkey": str(pubkey),
			"ids": ids
		})

	@autoretry
	def delete_messages(self, ids, pubkey=None):
		pubkey = self.refresh_token(pubkey)
		return self.make_request('delete_messages', {
			"pubkey": str(pubkey),
			"ids": ids
		})

	@autoretry
	def download_message(self, msgid):
		raise NotImplemented

	@autoretry
	def get_message_headers(self, msgid):
		raise NotImplemented
