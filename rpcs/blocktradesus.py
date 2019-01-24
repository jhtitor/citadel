"""

    Implements a BlockTrades.us API consumer,
    documented at https://blocktrades.us/api/v2/explorer/

"""
import logging
log = logging.getLogger(__name__)

import requests
import json

API_ENDPOINT = "https://api.blocktrades.us/v2/"

class BlockTradesUS_Exception(Exception):
	pass

class BlockTradesUS(object):
	
	def __init__(self, endpoint=None, origin=None, proxyUrl='socks5h://localhost:9150'):
		self.endpoint = endpoint or API_ENDPOINT
		self.origin = origin or None
		self.verify = True # SSL certificate checks
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

	def _make_url(self, _parts):
		return "/".join([ self.endpoint.strip('/') ] + _parts)

	def get_request(self, urlp, params={ }):
		log.debug("HTTP GET %s", self._make_url(urlp) )
		response = requests.get(
			self._make_url(urlp),
			proxies = self.proxies,
			headers = self.headers,
			verify = self.verify,
			params = params
		)
		#print(response.text)
		response = response.json()
		if 'error' in response:
			error = response['error']
			raise BlockTradesUS_Exception(error['message'], error['code'])
		return response

	def post_request(self, urlp, data={ }):
		log.debug("HTTP POST %s", self._make_url(urlp) )
		response = requests.post(
			self._make_url(urlp),
			proxies = self.proxies,
			headers = self.headers,
			verify = self.verify,
			json = data
		)
		if response.text == "Can not answer this request".strip():
			raise BlockTradesUS_Exception(response.text.strip())
		#print(response.text)
		response = response.json()
		if 'api_status' in response:
			raise BlockTradesUS_Exception(response['api_message'], response['api_code'])
		if 'error' in response:
			error = response['error']
			raise BlockTradesUS_Exception(error['message'], error['code'])
		return response

	# ### #

	def wallets(self, wallet_type=None):
		path = [ "wallets" ]
		if wallet_type:
			path.append(wallet_type)
		return self.get_request(path)
		""" Example response:
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

	def validate_address(self, wallet_type, address):
		return self.post_request(
			[ 'wallets', wallet_type, 'address-validator' ],
			{ 'address': address }
		)
		""" Example response:
		{
			'accountNumber': u'1.2.456100',
			'avatar': None,
			'correctAddress': None,
			'isAccount': None,
			'isBlacklisted': False,
			'isValid': True,
			'memoExpected': False,
			'memoPlaceholderText': None,
			'name': None
		},
		{
			'accountNumber': None,
			'avatar': None,
			'correctAddress': None,
			'isAccount': None,
			'isBlacklisted': None,
			'isValid': False,
			'memoExpected': None,
			'memoPlaceholderText': None,
			'name': None
		}
		"""

	def active_wallets(self):
		return self.get_request( ['active_wallets'] )
		""" Example response: [ 'bitshares2', 'bitcoin', ... ]
		"""

	def trading_pairs(self):
		return self.get_request(["trading-pairs"])
		""" Example response:
		[
			 {'inputCoinType': 'open.etp', 'outputCoinType': 'etp', 'rateFee': '0.'},
			 ...
		]
		"""
	
	def coins(self):
		return self.get_request([ "coins" ])
		""" Example response:
		[	{ coinType: "open.btc",
				walletName: "BitShares 2.0",
				name: "OpenLedger Bitcoin",
				symbol: "OPEN.BTC",
				walletSymbol: "OPEN.BTC",
				walletType: "bitshares2",
				transactionFee: 0. ,
				precision: 100000000. ,
				backingCoinType: btc,
				supportsOutputMemos: true,
				restricted: false,
				authorized: null,
				notAuthorizedReasons: null,
				gateFee: 0.00030,
				intermediateAccount: openledger-wallet,
				coinPriora: 0
			} , ...
		]
		"""

	def estimate_input_amount(self, outputAmount, inputCoinType, outputCoinType):
		r = self.get_request(
			['estimate-input-amount'],
			{
				'outputAmount': outputAmount,
				'inputCoinType': inputCoinType.lower(),
				'outputCoinType': outputCoinType.lower()
			}
		)
		# Hack -- openledger can return "[]" instead of useful data
		if isinstance(r, list) and len(r) == 0:
			return {
				"inputAmount": str(outputAmount),
				"inputCoinType": inputCoinType.lower(),
				"outputAmount": str(outputAmount), # 1:1
				"outputCoinType": outputCoinType.lower(),
			}
		""" Response example:
		{
			'inputAmount': '0.00003241',
 			'inputCoinType': 'btc',
 			'outputAmount': '1.00000000',
 			'outputCoinType': 'bts'
 		}
		"""

	def estimate_output_amount(self, inputAmount, inputCoinType, outputCoinType):
		r = self.get_request(
			[ 'estimate-output-amount' ],
			{
				'inputAmount': inputAmount,
				'inputCoinType': inputCoinType.lower(),
				'outputCoinType': outputCoinType.lower()
			}
		)
		# Hack -- openledger can return "[]" instead of useful data
		if isinstance(r, list) and len(r) == 0:
			return {
				"inputAmount": str(inputAmount),
				"inputCoinType": inputCoinType.lower(),
				"outputAmount": str(inputAmount), # 1:1
				"outputCoinType": outputCoinType.lower(),
			}
		return r
		""" Response example:
		{	'inputAmount': '1.00000000',
			'inputCoinType': 'btc',
			'outputAmount': '53472.61844',
			'outputCoinType': 'bts'
		}
		"""

	def deposit_limits(self, inputCoinType, outputCoinType):
		""" Returns deposit limit (in inputCoinType) """
		return self.get_request(
			[ 'deposit-limits' ],
			{
				'inputCoinType': inputCoinType.lower(),
				'outputCoinType': outputCoinType.lower()
			}
		)
		""" Response example:
		{
			'depositLimit': 0.66384368,
			'inputCoinType': "btc",
			'outputCoinType': "bts"
		}
		"""

	def transactions(self, inputAddress, inputCoinType=None, inputMemo=None):
		params = {
			'inputAddress': inputAddress,
		}
		if inputCoinType:
			params["inputCoinType"] = inputCoinType
		if inputMemo:
			params["inputMemo"] = inputMemo
		return self.get_request(
			['simple-api','transactions'],
			params
		)
		""" Response example:
		[
			{
			"transactionId": "5k6h7c67-k236-9akz-l1k2-sa97nj65h7s1",
			"transactionProcessingState": "output_transaction_broadcast", //'transaction_seen'
			"transactionFee": null,
			"rateFee": null,
			"inputFirstSeenTime": "2016-09-24T01:41:03.006532+00:00",
			"inputFullyConfirmedTime": "2016-09-24T01:41:03.006532+00:00",
			"inputNumberOfConfirmations": 1,
			"inputAmount": "0.01",
			"inputTransactionHash": "89asdfguhxc7459qw98djn3448vjlqkl49ed9e4f5a51cd6f2fe74841695eceee",
			"inputCoinType": "btc",
			"inputWalletType": "bitcoin",
			"inputAddress": "3LkZjha7k1nMajsd6JKHK7kkasd76jkaqE",
			"primarySourceAddress": null,
			"outputInitiationTime": "2016-09-24T01:41:03.006532+00:00",
			"outputAmount": "600.10329",
			"outputTransactionHash": "ui5sh81jkgha783kjua687af6984cba3f7e066c0",
			"outputCoinType": "bts",
			"outputWalletType": "bitshares2",
			"outputAddress": "fox",
			"outputAddressNickname": "unnamed_1",
			"lastModifiedTime": "2016-09-24T01:41:03.006532+00:00",
			"requiredNumberOfInputConfirmations": null,
			"inputUsdEquivalent": "4.92"
			}
		]
		"""

	def get_last_address(self, outputCoinType, outputAddress):
		params = {
			"coin": outputCoinType.lower(),
			"account": outputAddress
		}
		return self.post_request(['simple-api', 'get-last-address'], params)
		""" Response example: { "address": "SOME-INPUT-ADDRESS" } """

	def initiate_trade(self,
		inputCoinType,
		outputCoinType,
		outputAddress,
		refundAddress=None,
		outputMemo=None):
		arguments = {
			'inputCoinType': inputCoinType.lower(),
			'outputCoinType': outputCoinType.lower(),
			'outputAddress': outputAddress,
		}
		if refundAddress:
			arguments['refundAddress'] = refundAddress
		if outputMemo:
			arguments['outputMemo'] = outputMemo
		
		return self.post_request(['simple-api', 'initiate-trade'], arguments)
		""" Response example:
		{
			'inputAddress': "16vEbxHJKJ7JKm87m9aQMpoisdf7JK78zY",
			'inputMemo': "null",
			'inputCoinType': "btc",
			'outputAddress': "fox",
			'outputCoinType': "open.btc",
			'flatTransactionFeeInInputCoinType': 0.00000173,
			'refundAddress': "null",
		}
		"""
