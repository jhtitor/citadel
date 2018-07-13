"""

    Implements a Winex.pro version of BlockTrades.us API,
    documented at ... nowhere..?

    They don't support '/wallets' and '/transactions'
    at the very least.

"""
import requests
import json

API_ENDPOINT = "https://gateway.winexc.pro/api/v0/ol/support"

from .blocktradesus import BlockTradesUS, BlockTradesUS_Exception

class WinexPRO_Exception(BlockTradesUS_Exception):
	pass

class WinexPRO(BlockTradesUS):
	
	def reCache(self):
		if not(hasattr(self, 'cached_coins')):
			self.cached_coins = self.coins()

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
		# TODO: use winex latelyRecharge?address=bitshares_acc
		#           and/or latelyWithdraw?address=bitshares_acc
		return [ ]

	def deposit_limits(self, inputCoinType, outputCoinType):
		limit = 1000000000
		self.reCache()
		r = [ ]
		for c in self.cached_coins:
			if c['coinType'] == inputCoinType:
				limit = c['maxAmount']
				break
		return {
			'depositLimit': limit,
			'inputCoinType': inputCoinType,
			'outputCoinType': outputCoinType
		}
