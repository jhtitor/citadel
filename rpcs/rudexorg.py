"""

    Implements a RuDEX.org version of BlockTrades.us API,
    documented at ... nowhere..?

    The main difference between RuDEX and BlockTrades, is that
    the API is greatly simplified.
    The single call to '/coins' returns everything you need to
    know. There's no need to call '/wallets' or '/trading-pairs', etc.
    (TODO: Verify) There's no call to '/initiate-trade` as 
    all RuDEX tokens are on bitshares-like chains, meaning
    a) you can learn the name of intermediate-account in advance
    b) you can form the memo yourself using the extremely simplified
    gateway memo format (ESGM) [1]

    [1]: http://www.example.org/link_to_citadel_docs/
    //TODO: Fix this link

    This class, however, PRETENDS, that RuDEX has all those fancy
    BlockTrades capabilities, and represents the simplified data
    as compatible with the base API.

    Hopefully that explains why each call to `_some_rpc_method()`
    just yanks the global `cached_coins` array and forms appropriate
    response locally.
"""
import requests
import json

API_ENDPOINT = "https://gateway.rudex.org/api/v0_1/"

class RuDexORG_Exception(BaseException):
	pass

class RuDexORG(object):
	
	def __init__(self, endpoint=None, origin=None, proxyUrl='socks5h://localhost:9150'):
		self.endpoint = endpoint or API_ENDPOINT
		self.origin = origin or None
		self.proxies = {
			'http': proxyUrl,
			'https': proxyUrl,
		} if proxyUrl else None
		self.headers = {
			'Accept': 'application/json', 'Content-Type': 'application/json',
 			'User-Agent': "Mozilla/5.0 (Windows NT 6.1; rv:52.0) Gecko/20100101 Firefox/52.0"
		}
		if self.origin:
			self.headers['Origin'] = self.origin
			self.headers['Referer'] = self.origin
		
		self.cached_coins = None

	def _make_url(self, _parts):
		return "/".join([ self.endpoint.strip('/') ] + _parts)

	def get_request(self, urlp, params={ }):
		#print("HTTP GET", self._make_url(urlp) )
		response = requests.get(
			self._make_url(urlp),
			proxies = self.proxies,
			headers = self.headers,
			params = params
		)
		#print(response.text)
		response = response.json()
		if 'error' in response:
			error = response['error']
			raise BlockTradesUS_Exception(error['message'], error['code'])
		return response

	def post_request(self, urlp, data={ }):
		#print("HTTP POST", self._make_url(urlp) )
		response = requests.post(
			self._make_url(urlp),
			proxies = self.proxies,
			headers = self.headers,
			json = data
		)
		#print(response.text)
		response = response.json()
		if 'error' in response:
			error = response['error']
			raise BlockTradesUS_Exception(error['message'], error['code'])
		return response

	def _coin_request(self):
		return self.get_request(['coins'])
		""" RuDEX /coins request returns something like this: [
			{"name":"Peerplays",
			"description":"PeerPlays currency",
			"backingCoin":"PPY",
			"symbol":"PPY",
			"depositAllowed":true,
			"withdrawalAllowed":true,
			"memoSupport":true,
			"precision":5,
			"issuer":"rudex-ppy",
			"issuerId":"1.2.353611",
			"gatewayWallet":"rudex-gateway",
			"walletType":"peerplays",
			"minAmount":20000}, ... ]
		"""
	def reCache(self):
		if self.cached_coins is None:
			self.cached_coins = self._coin_request()

	# ### #
	def wallets(self, walletType=None):
		if walletType:
			walletType = walletType.lower()

		self.reCache( )
		r = [ ]
		for c in self.cached_coins:
			w = {
				"defaultAddressType": 'shared_address_with_memo',
				"extraData": { },
				'name': c['name'],
				'supportsInputToSharedAddressWithMemo': True,
				'supportsInputToUniqueAddress': False,
				'walletType': c['walletType']
			}
			# single-wallet return
			if walletType and walletType == w['walletType']:
				return w
			r.append(w)
		w = {
			"defaultAddressType": 'shared_address_with_memo',
			"extraData": { },
			'name': "BitShares 2.0",
			'supportsInputToSharedAddressWithMemo': True,
			'supportsInputToUniqueAddress': False,
			'walletType': "bitshares2"
		}
		if walletType and walletType == w['walletType']:
			return w
		r.append(w)
		
		if walletType:
			return None
		return r
		""" What we want:
		{
			'defaultInputAddressType': 'unique_address',
			'extraData': {
				'addresses': {'classification': 'address',
				'pubkey_hash_address_prefix': 0,
				'script_hash_address_prefix': 5,
				'type': 'base58',
				'wif_prefix': 128
			},
			'block_explorer': {
					'address': 'https://blockchain.info/address/${address}',
					'block_number': 'https://blockchain.info/block-height/${block_number}',
					'transaction_hash': 'https://blockchain.info/tx/${transaction_hash}'},
					'default_coin_type': 'btc',
					'uri': {'address': 'bitcoin:${address}'}
			},
			'name': 'Bitcoin',
			'supportsInputToSharedAddressWithMemo': False,
			'supportsInputToUniqueAddress': True,
			'walletType': 'bitcoin'
		}
		"""

	def valid_graphene_address(self, address):
		# TODO: check for a-z0-9\-, what else can we really do
		return True

	def validate_address(self, wallet_type, address):
		# HACK!
		# There's no address validator on RuDEX,
		# but we can probably do it on our own
		if not self.valid_graphene_address(address):
			return {
			'accountNumber': None,
			'avatar': None,
			'correctAddress': False,
			'isAccount': False,
			'isBlacklisted': None,
			'isValid': False,
			'memoExpected': None,
			'memoPlaceholderText': None,
			'name': None
			}
		# we don't have any real data, but we can approximate
		return {
			'accountNumber': None,
			'avatar': None,
			'correctAddress': True,
			'isAccount': True,
			'isBlacklisted': None,
			'isValid': True,
			'memoExpected': None,
			'memoPlaceholderText': None,
			'name': address,
			}
	
	def active_wallets(self):
		self.reCache( )
		r = [ ]
		for c in self.cached_coins:
			r.append(c['walletType'])
		return r

	def trading_pairs(self):
		self.reCache( )
		r = [ ]
		for c in self.cached_coins:
			ctid = c["symbol"].lower()
			if c["symbol"] == c["backingCoin"]: # PPY case
				ctid = "." + c["symbol"].lower()
			tp = {
				"inputCoinType": ctid, #c["symbol"].lower(),
				"outputCoinType": c["backingCoin"].lower(),
			}
			r.append(tp)
			tp = {
				"inputCoinType": c["backingCoin"].lower(),
				"outputCoinType": ctid, #c["symbol"].lower(),
			}
			r.append(tp)
		return r

	def coins(self, coinType=None):
		if coinType:
			coinType = coinType.lower()
		self.reCache( )
		r = [ ]
		for c in self.cached_coins:
			ctid = c["symbol"].lower()
			if c["symbol"] == c["backingCoin"]: # PPY case
				ctid = "." + c["symbol"].lower()
			# symbol -> backing coin
			ct = {
				"coinType": ctid, #c["symbol"].lower(),
				"walletName": c["walletType"], # :(
				"name": c["description"],
				"symbol": c["symbol"],
				"walletSymbol": c["symbol"],
				"walletType": "bitshares2", #c["walletType"].lower(),
				"transactionFee": 0.,
				"precision": pow(10, c["precision"]),
				"backingCoinType": c["backingCoin"].lower(),
				"supportsOutputMemos": False,
				"restricted": False,
				"authorized": None,
				"notAuthorizedReasons": None,
				"gateFee": 0.,
				"intermediateAccount": c["gatewayWallet"],
				"coinPriora": 0
			}
			# hack - single coin
			if coinType and ct["coinType"] == coinType:
				return ct
			r.append(ct)
			# backing coin -> symbol
			ct = {
				"coinType": c["backingCoin"].lower(),
				"walletName": c["walletType"], # :(
				"name": c["description"],
				"symbol": c["backingCoin"],
				"walletSymbol": c["backingCoin"],
				"walletType": c["walletType"].lower(),
				"transactionFee": 0. ,
				"precision": pow(10, c["precision"]),
				"backingCoinType": None,
				"supportsOutputMemos": False,
				"restricted": False,
				"authorized": None,
				"notAuthorizedReasons": None,
				"gateFee": 0.,
				"intermediateAccount": c["gatewayWallet"],
				"coinPriora": 0
			}
			# hack - single coin
			if coinType and ct["coinType"] == coinType:
				return ct
			r.append(ct)
		if coinType:
			return None
		return r

	def estimate_input_amount(self, outputAmount, inputCoinType, outputCoinType):
		self.reCache()
		#TODO: check if this is a valid trading pair
		return {
			'inputAmount': str(outputAmount), # input is same as output!
 			'inputCoinType': inputCoinType,
 			'outputAmount': outputAmount,
 			'outputCoinType': outputCoinType
 		}

	def estimate_output_amount(self, inputAmount, inputCoinType, outputCoinType):
		self.reCache()
		#TODO: check if this is a valid trading pair
		return {
			'inputAmount': inputAmount,
			'inputCoinType': inputCoinType,
			'outputAmount': str(inputAmount), # same as input
			'outputCoinType': outputCoinType
		}

	def deposit_limits(self, inputCoinType, outputCoinType):
		# No way to query the limits, return something big :(
		return {
			'depositLimit': 1000000000,
			'inputCoinType': inputCoinType,
			'outputCoinType': outputCoinType
		}

	def transactions(self, inputAddress, inputCoinType=None, inputMemo=None):
		# No such data available :(
		return [ ]

	def initiate_trade(self,
		inputCoinType,
		outputCoinType,
		outputAddress,
		refundAddress=None,
		outputMemo=None):
		if inputCoinType.startswith("."):
			inputCoinType = inputCoinType[1:]
		if outputCoinType.startswith("."):
			outputCoinType = outputCoinType[1:]
		# We must do it ourselves
		self.reCache( )
		r = [ ]
		coin = None
		ldir = "symbol"
		rdir = "backingCoin"
		for c in self.cached_coins:
			if inputCoinType.upper() == c["symbol"] and outputCoinType.upper() == c["backingCoin"]:
				if not(c["withdrawalAllowed"]):
					raise Exception("Withdrawal not allowed")
				coin = c
				break
			if outputCoinType.upper() == c["symbol"] and inputCoinType.upper() == c["backingCoin"]:
				if not(c["depositAllowed"]):
					raise Exception("Deposit not allowed")
				coin = c
				rdir = "symbol"
				ldir = "backingCoin"
				break
		if not coin:
			raise Exception("Not found")
		return {
			'inputAddress': c["gatewayWallet"],
			'inputMemo': "dex:" + outputAddress,
			'inputCoinType': inputCoinType,
			'outputAddress': outputAddress,
			'outputCoinType': outputCoinType,
			'flatTransactionFeeInInputCoinType': 0.,
			'refundAddress': None,
		}
