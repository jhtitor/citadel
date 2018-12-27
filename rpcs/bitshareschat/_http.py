import requests
import requests.exceptions
import datetime

from .rpcbase import BitSharesChatRPC
from .rpcbase import(
	ChatRPCException,
	TokenExpired,
	APIError,
	DiscoveryFailed,
	ConnectionError,
)
from .rpcbase import AD_HEADER, AD_HEADER_WS
import re # for HTML "parsing"

GET ="GET" ; POST="POST" ; PUT ="PUT" ; HEAD="HEAD"

class BitSharesChatAuthToken:
	def __init__(self, token_key, expire_seconds):
		self.token_key = token_key
		self.expires = (datetime.datetime.now() +
				datetime.timedelta(seconds=expire_seconds))
	def __str__(self):
		return self.token_key
	def expired(self):
		return self.expires < datetime.datetime.now()

class BitSharesChatHTTP(BitSharesChatRPC):
	def __init__(self, *args, proxyUrl=None, **kwargs):
		super(BitSharesChatHTTP, self).__init__(*args, **kwargs)
		self.tokens = { }
		self.config = None
		self.proxies = {
			'http': proxyUrl,
			'https': proxyUrl,
		} if proxyUrl else None

	@property
	def authed_keys(self):
		for pub in self.tokens:
			yield pub

	def autoDiscover(self, url):
		if self.discovered: return
		h, w = self.__class__.discover(url, self.proxies['http'] if self.proxies else None)
		self.url = h
		self.discovered = True

	def web_discover(self, url):
		try:
			response = requests.get(url,
				proxies = self.proxies,
				headers = self.headers)
		except:
			raise ConnectionError
		
		h_url = w_url = None
		if AD_HEADER in response.headers:
			h_url = response.headers[AD_HEADER]
		if AD_HEADER_WS in response.headers:
			w_url = response.headers[AD_HEADER_WS]
		if h_url:
			return (h_url, w_url)
		
		body = response.text
		links = re.findall('<link(.*?)/{0,1}>', body)
		for link in links:
			ref_ = re.match("rel=(\"|')(.+?)(\"|')", link)
			href_ = re.match("href=\"|'(.+?)\"|'", link)
			if ref_ and href_:
				k = ref_.group(1)
				v = href_.group(1)
				
				if k.lower() == AD_HEADER.lower():
					h_url = v
				if k.lower() == AD_HEADER_WS.lower():
					w_url = v
				
		if h_url:
			return (h_url, w_url)
		
		raise DiscoveryFailed

	def _make_url(self, _parts):
		if isinstance(_parts, str): _parts = _parts.split("/")
		parts = [ self.url.strip('/') ]
		for i, _part in enumerate(_parts):
			_parts[i] = _parts[i].strip('/')
		parts.extend(_parts)
		return "/".join(parts)

	def make_request(self, path, data, method=GET, files=None,
			as_file=False,
			autodiscover=False):
		
		if autodiscover: self.autoDiscover()
		headers = dict(self.headers)
		
		# Methods
		params = data
		json = None
		fdata = None
		if (method in [ POST, PUT ]):
			params = None
			json = data
		if files:
			params = None
			json = None
			fdata = data
			headers.pop('Content-Type')#] = 'multipart/form-data'
		if as_file:
			headers.pop('Accept')
		
		url = self._make_url(path)
		#print("* HTTP", url, params, json)
		try:
			response = requests.request(method, url,
				headers = headers,
				proxies = self.proxies,
				params = params,
				json = json,
				data = fdata,
				files = files,
				stream = bool(as_file)
			)
		except requests.exceptions.ConnectionError as e:
			raise ConnectionError(e)
		if response.status_code == 403:
			tok = data["token"] if "token" in data else None
			raise TokenExpired(tok)

		if as_file:
			if isinstance(as_file, int) and as_file > 1:
				return response.iter_content(chunk_size=as_file)
			return response.content
		
		if (method == HEAD):
			return response.headers
		
		try:
			resp = response.json()
		except:
			print(response.text)
			raise
		
		if 'error' in resp:
			raise APIError(resp['error']['message'], code=resp['error']['code'])
		
		return resp

	# Token Management
	
	def token_expired(self, pubkey):
		if not pubkey in self.tokens: return True
		token = self.tokens[pubkey]
		return token.expired()
	
	def set_token(self, pubkey, token_key, expire_seconds):
		token = BitSharesChatAuthToken(token_key, expire_seconds)
		self.tokens[pubkey] = token
	
	def refresh_token(self, pubkey=None):
		pubkey = str(self.guessKey(pubkey))
		if not(self.token_expired(pubkey)):
			return str(self.tokens[pubkey])
		chal = self.get_challenge(pubkey)
		memo = chal['challenge']
		cleartext = self.decodeMemo(**memo)
		tok = self.send_response(chal['key'], cleartext)
		self.set_token(pubkey, tok["token"], tok["expires_in"])
		return tok["token"]
	
	def autoretry(func):
		""" If method has a call to `self.refresh_token()`,
		    consider adding @autoretry decorator. """
		def func_wrapper(self, *args, **kwargs):
			try:
				return func(self, *args, **kwargs)
			except TokenExpired as e:
				if not self.autorefresh: raise
				self.tokens.pop(e.token, None) # unset token
			return func(self, *args, **kwargs)
		return func_wrapper
	
	# LOGIN METHODS
	
	def get_challenge(self, pubkey):
		return self.make_request(['challenge'], {
			"pubkey": str(pubkey)
		})
	
	def send_response(self, authkey, response):
		return self.make_request(['challenge'], {
			"key": authkey,
			"response": response
		}, POST)
	
	def _valid_tokens(self):
		r = [ ]
		for pubkey in self.tokens:
			tok = self.tokens[pubkey]
			if not tok.expired():
				r.append( tok )
		return r
	def _any_token(self):
		if len(self.privkeys) > 1:
			raise Exception("This object has to many keys attached.")
		tokens = self._valid_tokens()
		return str(tokens[0]) if len(tokens) > 0 else None

	def status(self, tokenkey=None):
		data = { }
		if tokenkey is None:
			tokenkey = self._any_token()
		if tokenkey:
			data["token"] = str(tokenkey)
		return self.make_request(['status'], data)
	
	def motd(self):
		return self.make_request(['motd'], { })
	
	# MAIN METHODS
	
	@autoretry
	def get_messages(self, start="", limit=100, either="", pubkey=None):
		return self.make_request(['messages'], {
			"token": self.refresh_token(pubkey),
			"start": start,
			"limit": limit,
			"either": either,
		})

	@autoretry
	def post_memo(self, memo):
		""" Send previously prapared memo object. """
		pubkey = memo["from"]
		return self.make_request(['messages'], {
			"token": self.refresh_token(pubkey),
			"memo": memo
		}, PUT)

	@autoretry
	def post_message(self, to_pubkey, clear_text, pubkey=None):
		""" Prepare new memo object and send it. """
		if pubkey is None:
			pubkey = memo["from"]
		return self.make_request(['messages'], {
			"token": self.refresh_token(pubkey),
			"memo": self.encodeMemo(to_pubkey, clear_text)
		}, PUT)

	@autoretry
	def post_filememo(self, filememo, metamemo, pubkey=None):
		""" Send two memo messages (file and meta) as HTTP upload. """
		if pubkey is None:
			pubkey = filememo["from"]
		return self.make_request(['files'], {
			"token": self.refresh_token(pubkey),
			"file_to":   filememo["to"],
			"file_from": filememo["from"],
			"file_nonce":filememo["nonce"],
			"meta_to":      metamemo["to"],
			"meta_from":    metamemo["from"],
			"meta_nonce":   metamemo["nonce"],
			"meta_message": metamemo["message"],
		}, PUT, files={"file_message": filememo['message']})

	@autoretry
	def verify_messages(self, ids, pubkey=None):
		return self.make_request(['verify_messages'], {
			"token": self.refresh_token(pubkey),
			"ids": ids
		}, POST)

	@autoretry
	def delete_messages(self, ids, pubkey=None):
		return self.make_request(['delete_messages'], {
			"token": self.refresh_token(pubkey),
			"ids": ids
		}, POST)

	@autoretry
	def download_message(self, msgid, pubkey=None):
		return self.make_request(['messages', msgid],
			{ "token": self.refresh_token(pubkey)
		}, as_file=True)

	@autoretry
	def get_message_headers(self, msgid, pubkey=None):
		r = { }
		h = self.make_request(['messages', msgid],
			{ "token": self.refresh_token(pubkey)
		}, HEAD)
		for k, v in h.items():
			k = k.lower()
			if k.startswith("x-bitshares2-"):
				k = k[len("x-bitshares2-"):]
				if k.startswith("memo-"):
					k = k[len("memo-"):]
					r[k] = v
		return r

