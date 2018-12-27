"""

	Implements a BitShares-UI faucet API

"""
import requests

class BTSFaucet(object):

	def __init__(self, endpoint, origin=None, proxyUrl='socks5h://localhost:9150'):
		self.endpoint = endpoint
		self.origin = origin
		self.proxies = {
			'http': proxyUrl,
			'https': proxyUrl,
		} if proxyUrl else None
		self.headers = {
			'Accept': 'application/json', 'Content-Type': 'application/json',
			'User-Agent': "Mozilla/5.0 (Windows NT 6.1; rv:52.0) Gecko/20100101 Firefox/52.0"
		}
		self.url = self._make_url(['/api/v1/accounts'])
	
	def _make_url(self, _parts):
		parts = [ self.endpoint.strip('/') ]
		for i, _part in enumerate(_parts):
			_parts[i] = _parts[i].strip('/')
		parts.extend(_parts)
		return "/".join(parts)
	
	def post_request(self, data):
		response = requests.post(
			self.url,
			proxies = self.proxies,
			headers = self.headers,
			json = data,
		)
		if response.text.startswith('<!DOCTYPE'):
			raise Exception("Response is not JSON, could be Cloudflare/CAPTCHA page or some other gateway error.")
		
		resp = response.json()
		#from pprint import pprint
		#pprint(resp)
		if 'error' in resp:
			try:
				for tag,arr in resp['error'].items():
					errmsg = arr[0]
			except:
				errmsg = "unknown error"
			raise Exception(errmsg)
		
		return resp

	def register(self, name, owner_key, active_key, memo_key, refcode=None, referrer=None):	
		data = { "account": {
			"name": name,
			"owner_key": owner_key,
			"active_key": active_key,
			"memo_key": memo_key,
			"refcode": refcode,
			"referrer": referrer
		} }
		#import json
		#print (json.dumps(data));
		return self.post_request(data)['account']


if  __name__ == "__main__":
	name, url, refurl = KnownFaucets[0]
	f = BTSFaucet( url, refurl )

	f.register("suspender", "BTSpubkeyowner", "BTSpubkeyactive", "BTSpubkeymemo")
