"""

    Implements an xbts.io version of BlockTrades.us API,
    documented at ... nowhere..?

    They don't support '/wallets' and '/transactions'
    at the very least.

"""
import requests
import json

API_ENDPOINT = "https://apis.xbts.io/api/v1/"

from .blocktradesus import BlockTradesUS, BlockTradesUS_Exception

class XBtsIO_Exception(BlockTradesUS_Exception):
	pass

class XBtsIO(BlockTradesUS):

	def reCache(self):
		self.verify = False # hack, disable SSL checks
		if not(hasattr(self, 'cached_coins')):
			self.cached_coins = self.coin()

	def coin(self):
		# xbts.io calls this method "coin", not "coins"
		return self.get_request([ "coin" ])

	### ###
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
				"intermediateAccount": c["issuer"],
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
				"intermediateAccount": c["issuer"],
				"coinPriora": 0
			}
			# hack - single coin
			if coinType and ct["coinType"] == coinType:
				return ct
			r.append(ct)
		if coinType:
			return None
		return r

	# ### #
	def wallets(self, walletType=None):
		if walletType:
			walletType = walletType.lower()
		
		self.reCache()
		r = [ ]
		for c in self.cached_coins:
			w = {
				"defaultAddressType": 'unique_address',
				"extraData": { },
				'name': c['name'],
				'supportsInputToSharedAddressWithMemo': False,
				'supportsInputToUniqueAddress': True,
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

	def transactions(self, inputAddress, inputCoinType=None, inputMemo=None):
		# TODO: use xbts latelyRecharge?address=bitshares_acc
		#           and/or latelyWithdraw?address=bitshares_acc
		return [ ]

	def deposit_limits(self, inputCoinType, outputCoinType):
		limit = 1000000000
		#self.reCache()
		#r = [ ]
		#for c in self.cached_coins:
		#	print(c['symbol'], 'vs', inputCoinType, 'vs', c['backingCoin'])
		#	if c['backingCoin'].lower() == inputCoinType.lower():
		#		limit = c['withdrawFee']
		#		break
		#	if c['symbol'].upper() == inputCoinType.upper():
		#		limit = c['depositFee']
		#		break
		return {
			'depositLimit': limit,
			'inputCoinType': inputCoinType,
			'outputCoinType': outputCoinType
		}

	def _match_coin(self, inputCoinType):
		self.reCache()
		#print("MATCH COIN", inputCoinType)
		for c in self.cached_coins:
			#print(c['symbol'], 'vs', inputCoinType, 'vs', c['backingCoin'])
			if c['backingCoin'].lower() == inputCoinType.lower():
				return c, 1
			if c['symbol'].lower() == inputCoinType.lower():
				return c, 2
		return None, None

	def estimate_input_amount(self, outputAmount, inputCoinType, outputCoinType):
		c, wd = self._match_coin(inputCoinType)
		#print(c, wd)
		#self.reCache()
		#TODO: check if this is a valid trading pair
		return {
			'inputAmount': str(outputAmount), # input is same as output!
			'inputCoinType': inputCoinType,
			'outputAmount': outputAmount,
			'outputCoinType': outputCoinType
		}

	def estimate_output_amount(self, inputAmount, inputCoinType, outputCoinType):
		#self.reCache()
		amt = float(inputAmount)
		c, wd = self._match_coin(inputCoinType)
		#print(">>>>>>>>>", wd, "<<<<<<")
		fee = 0
		if wd == 1:
			#print("Grab deposit fee", c)
			fee = c['depositFee'] / pow(10, c['precision'])
		if wd == 2:
			#print("Grab witdhraw fee", c)
			fee = c['withdrawFee'] / pow(10, c['precision'])
		amt -= fee
		#TODO: check if this is a valid trading pair
		return {
			'inputAmount': inputAmount,
			'inputCoinType': inputCoinType,
			'outputAmount': str(amt), # same as input
			'outputCoinType': outputCoinType
		}

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
		
		r = self.post_request(['simple-api', 'initiate-trade'], arguments)
		if r['inputAddress'] is None:
			c, wd = self._match_coin(inputCoinType)
			r['inputAddress'] = c['issuer']
			r['inputMemo'] = c['backingCoin'].lower()+':'+outputAddress
		return r
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

