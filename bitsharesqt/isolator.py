"""
	This class wraps `BitShares` to provide a sandbox environment.
	
	You MUST first call:
	
		from isolator import BitsharesIsolator
		BitsharesIsolator.enable()
	
	This will set a shared_blockchain_instance to broken, unusable
	object, so all `get_shared_blockchain_instance` consumers will
	fail with an Exception upon creation.
	
	This should ensure no rogue instances of BitShares are created
	with calls like:
	
		asset = Asset("BTS") # <- no bitshare_instance= provided(!)
	
	UNLESS your application calls `set_shared_blockchain_instance`
	later!
	
	Then, to create/get a singleton instance, use
	
		iso = BitsharesIsolator() # (you may pass BitShares constructor args,kwargs)
		bitshares = iso.bts
	
	Note, that the isolator will ALWAYS set offline=True, so that
	the BitSharesRPC does not connect automatically. Therefore, you MAY call
	
		iso.connect(url) # regular BitSharesRPC.connect arguments
	
"""
import logging
log = logging.getLogger(__name__)

class BrokenBitsharesInstance():
	def __init__(self, *args, **kwargs):
		pass
	
	def __getattr__(self, name):
		raise ValueError("Attempting to use BrokenBitsharesInstance")

class ResourceUnavailableOffline(Exception):
	pass

class TimeOut(Exception):
	pass

class WalletLocked(Exception):
	pass

from .netloc import Cancelled

class BitsharesIsolator(object):
	enabled = False
	@classmethod
	def enable(self):
		if not self.enabled:
			from bitshares.instance import set_shared_blockchain_instance
			broken = BrokenBitsharesInstance()
			set_shared_blockchain_instance(broken)
			self.enabled = True
	
	def __init__(self, *args, **kwargs):
		import bitshares
		kwargs.pop('offline', None) # overwrite
		
		self.mainwin = None
		
		self.ping_callback = kwargs.pop("ping_callback", None)
		
		self.conn_node = kwargs.pop('node', "")
		self.conn_rpcuser = kwargs.pop('rpcuser', "")
		self.conn_rpcpassword = kwargs.pop('rpcpassword', "")
		
		#self.bts = lambda: 0 #bitshares.BitShares(*args, offline=True, **kwargs)
		self.bts = bitshares.BitShares(*args, offline=True, wallet=None, config_store=None, **kwargs)
		self.bts.rpc = None
		self.store = None
		self.offline = True
		
		self.subscribed_accounts = set()
		self.subscribed_markets = set()
		
		self.minicache_accnames = {} # 1.2.ID to name
		self.minicache_precision = {} # SYMBOL to precision
		self.fave_coinnames = set() # semi-random
		self.fave_markets = set() # same
		
		#from bitsharesapi.bitsharesnoderpc import BitSharesNodeRPC
	
	def setMainWindow(self, win):
		self.mainwin = win

	def disconnect(self):
		return self.close(force=True)
		
	def close(self, force=False):
		if self.offline and not(force):
			return True
		try:
			if self.bts.rpc:
				self.bts.rpc.close()
		except:
			pass
		self.bts.rpc = None
		self.offline = True
		
	def connect(self, *args, **kwargs):
		self.close(force=True)
		
		#import bitshares
		#self.bts = bitshares.BitShares(offline=True, storage=self.store)
		#from bitsharesapi.bitsharesnoderpc import BitSharesNodeRPC
		#self.bts.rpc = BitSharesNodeRPC(*args, **kwargs)
		#self.bts.rpc.connect(*args, **kwargs)
		import bitsharesextra.bitsharesnoderpc as rpcextra
		kwargs["node_class"] = rpcextra.BitSharesNodeRPC
		self.bts.connect(*args, **kwargs)
		self.offline = False
		
		self.bts.rpc.set_subscribe_callback(1, False)
	
	def is_connected(self):
		if self.offline:
			return False
		
		if not self.bts.rpc:
			return False
		
		return self.bts.rpc.connected
	
	def is_connecting(self):
		if not self.bts.rpc:
			return False
		
		return self.bts.rpc.connecting
	
	def chain_prefix(self):
		if self.is_connected():
			return self.bts.rpc.chain_params["prefix"]
		return "BTS"
	
	def get_proxy_config(self):
		config = self.bts.config
		proxyOn = config.get('proxy_enabled', False)
		if not proxyOn:
			return None
		proxyAuth = config.get('proxy_auth_enabled', False)
		proxyHost = config.get('proxy_host', None)
		proxyPort = config.get('proxy_port', 9150)
		proxyType = config.get('proxy_type', "socks5")
		proxyUser = config.get('proxy_user', None)
		proxyPass = config.get('proxy_pass', None)
		authUrl = ""
		if proxyAuth and (proxyUser or proxyPass):
			authUrl = ((proxyUser if proxyUser else "") + ":" +
				    (proxyPass if proxyPass else "")) + "@"
		proxyUrl = None
		if proxyHost:
			proxyUrl = str(proxyType) + "://" + authUrl + str(proxyHost) + ":" + str(proxyPort)
		return proxyUrl
	
	def setWallet(self, wallet):
		if wallet is None:
			self.close()
			self.bts.wallet = None
			return
		
		self.bts.wallet = wallet
	
	def setStorage(self, storage):
		self.store = storage
		if storage is None:
			self.bts.config = { }
			self.accountStorage = { }
			self.assetStorage = { }
		else:
			self.bts.config = storage.configStorage
			self.accountStorage = self.store.accountStorage
			self.assetStorage = self.store.assetStorage
	
	def flush_notes(self):
		if not self.bts.rpc:
			return [ ]
		return self.bts.rpc.flush_notes()
	
	def storeBalances(self, account_name, blnc):
		store = self.store.accountStorage
		#import json
		#graphene_json = store.getByName(account_name);
		#print(aku)
		#graphene_json = json.loads(store.getByName(account_name)['raw'])
		#graphene_json['balances'] = blnc
		#store.updateRawJSON(account_name, json.dumps(blnc))
		store.update(account_name, 'balances_json', blnc)
	
	def injectBalance(self, account_id, asset_symbol, amount_int):
		iso = self
		store = self.store.accountStorage
		account = self.getAccount(account_id, force_remote=False)
		asset = self.getAsset(asset_symbol)
		value = int(amount_int) / pow(10, asset["precision"])
		acc_blnc = iso.getBalances(account)
		blnc = { }
		for o in acc_blnc:
			blnc[o.symbol] = str(o).split(" ")[0]
		blnc[asset_symbol] = value
		#print("Post-inject", blnc)
		self.storeBalances(account["name"], blnc)
		account._balances = blnc
		return account
	
	def getBlindPublicKeys(self):
		accs = self.getBlindAccounts()
		pubs = [ ]
		for acc in accs:
			pubs.append(acc[1])
		return pubs

	def removeUselessKeys(self, account_id):
		blind_pubs = self.getBlindPublicKeys()
		pubs = self.getLocalAccountKeys(account_id)
		removed = 0
#		privs = self.getPrivateKeyForPublicKeys(pubs)
#		for i in range(0, len(pubs)):
#			pub = pubs[i]
#			priv = privs[i]
		for pub in pubs:
			try:
				priv = self.getPrivateKeyForPublicKeys([pub])[0]
			except:
				priv = None
			if str(pub) in blind_pubs:
				continue
			if not(self.bts.wallet.getAccountFromPublicKey(pub)):
				self.bts.wallet.removePrivateKeyFromPublicKey(pub)
				removed += 1
		
		return removed
	
	def getRemoteAccounts(self):
		if self.offline or not self.bts.wallet.rpc:
			raise ResourceUnavailableOffline()
		
		names = set()
		accounts = self.bts.wallet.getAccounts()
		
		for account in accounts:
			if account is None: # !?
				continue
			if account['name']:
				names.add(account['name'])
		
		return list(names)
	
	def countStoredPrivateKeys(self, account_id, update=False):
		accountStorage = self.store.accountStorage
		keyStorage = self.store.keyStorage
		account = self.getAccount(account_id)
		pubs = self.getLocalAccountKeys(account_id)
		nkeys = self.store.countPrivateKeys(pubs)
		if update:
			accountStorage.update(acc["name"], "keys", nkeys)
		return nkeys
	
	def isCachedAccount(self, account_id):
		accountStorage = self.store.accountStorage
		try:
			if account_id.startswith('1.2.'):
				acc = accountStorage.getById(account_id)
			else:
				acc = accountStorage.getByName(account_id)
		except:
			import traceback
			traceback.print_exception()
			return False
		return True if acc else False
	
	def getCachedAccounts(self):
		accountStorage = self.store.accountStorage
		accs = accountStorage.getAccounts()
		return list(accs)
	
	def getBlindAccounts(self):
		return self.store.blindAccountStorage.getAccounts()
	
	def _accountFromDict(self, account_id, accountInfo):
		from bitshares.account import Account
		
		account = Account.__new__(Account)
		account.identifier = account_id
		account.blockchain = self.bts
		account.account_id = account_id
		account.cached = True
		account.full = True
		#	blockchain_instance=self.bts,
		#account = Account(accountInfo)
		for key, val in accountInfo.items():
			if key == "balances":
				key = "_balances"
			try:
				setattr(account, key, val)
			except Exception as e:
				if not(key in ["name"]):
					print(str(e), key, val)
			account[key] = val
		
		return account
	
	def getLocalAccountKeys(self, account_id):
		account = self.getAccount(account_id)
		pubs = [ ]
		for authority in account["active"]["key_auths"]:
			pubs.append(authority[0])
		for authority in account["owner"]["key_auths"]:
			pubs.append(authority[0])
		pubs.append( account["options"]["memo_key"] )
		return pubs
	
	def getPrivateKeyForPublicKeys(self, pubs):
		if self.bts.wallet.locked():
			raise WalletLocked()
		privs = [ ]
		for pub in pubs:
			privs.append(
			self.bts.wallet.getPrivateKeyForPublicKey(pub)
			)
		return privs
	
	def getAccountFromPublicKey(self, pubkey):
		account_names = self.getCachedAccounts()
		for account_name in account_names:
			pubs = self.getLocalAccountKeys(account_name)
			if pubkey in pubs:
				return account_name
		raise KeyError("Account with key " + pubkey)
	
	def removeCachedAccount(self, account_name):
		accountStorage = self.store.accountStorage
		accountStorage.delete(account_name)
	
	def getAccount(self, account_id, force_remote=False, force_local=False, cache=False):
		
		if account_id.startswith("1.2."):
			accountInfo = self.accountStorage.getById(account_id) if self.store else None
		else:
			if account_id.startswith("BTS"): # looks like a pubkey
				try: # try to match it locally, but not too hard
					account_id = self.getAccountFromPublicKey(account_id)
				except:
					import traceback
					traceback.print_exc()
					pass
			accountInfo = self.accountStorage.getByName(account_id) if self.store else None
		
		if force_local:
			if accountInfo:
				return self._accountFromDict(account_id, accountInfo)
			return None
		
		from bitshares.account import Account
		# TODO: remove "force_remote" completely
		if not accountInfo or force_remote:
			if self.offline:
				raise ResourceUnavailableOffline("Account %s" % str(account_id))
			if account_id.startswith("BTS"): # looks like public key
				try: # maybe node knows something
					account_id = self.bts.wallet.getAccountFromPublicKey(account_id)
				except:
					import traceback
					traceback.print_exc()
					pass
			account = Account(account_id, blockchain_instance=self.bts)
			
			if cache:
				self.storeAccount(account)
			
			account["keys"] = "" # unknown
			return account
		
		account = self._accountFromDict(account_id, accountInfo)
		
		return account
	
	def getAsset(self, asset_id, cache=True, force_remote=False, force_local=False):
		from bitshares.asset import Asset
		
		if not(force_remote):
			if asset_id.startswith('1.3.'):
				stored_asset = self.assetStorage.getById(asset_id) if self.store else None
			else:
				stored_asset = self.assetStorage.getBySymbol(asset_id) if self.store else None
		else:
			stored_asset = None
		
		if stored_asset:
			stored_asset["precision"] = int(stored_asset["precision"])
			stored_asset["options"]["max_supply"] = int(stored_asset["options"]["max_supply"])
			forged_asset = Asset.__new__(Asset)
			forged_asset.identifier = stored_asset["id"]
			forged_asset.blockchain = self.bts
			forged_asset.cached = True
			forged_asset.lazy = True
			forged_asset.full = False
			forged_asset.asset = stored_asset["symbol"]
			for k, v in stored_asset.items():
				forged_asset[k] = v
			self.minicache_precision[stored_asset["symbol"]] = stored_asset["precision"]
			return forged_asset
		
		if self.offline or force_local: # Can't or Won't fetch remote asset
			raise ResourceUnavailableOffline("Asset %s" % str(asset_id))
		
		from bitshares.exceptions import AssetDoesNotExistsException
		try:
			remote_asset = Asset(asset_id, full=True, lazy=False, blockchain_instance=self.bts)
		except AssetDoesNotExistsException:
			raise
		except:
			raise ResourceUnavailableOffline("Asset %s" % str(asset_id))
		
		if cache:
			self.saveAsset(remote_asset)
		
		return remote_asset
	
	def storeAccount(self, account, keys=2):
		iso = self
		accountStore = iso.accountStorage
		jsond = { }
		for key, val in account.items():
			jsond[key] = val
		
		if "balances" in jsond:
			jsond.pop("balances")
		
		blnc = { }
		for amount in self.getBalances(account['id'], force_local=True):
			blnc[str(amount.symbol)] = str(amount).split(" ")[0]
		
		try:
			accountStore.add(account['name'], account['id'], keys=keys)
		except ValueError: # already exists
			#accountStore.update(account['name'], 'keys', keys)
			pass # it's ok
		accountStore.update(account['name'], 'graphene_json', jsond)
		accountStore.update(account['name'], 'balances_json', blnc)
	
	def saveAsset(self, asset):
		store = self.assetStorage
		exists = store.getById(asset['id'])
		if exists:
			store.update(asset['id'], asset)
		else:
			store.add(asset['id'], asset['symbol'], asset)
	
	class QAmount():
		def __init__(self, asset, amount, precision=None, delim=","):
			if type(amount) == int:
				pass
			if type(amount) == float and precision is None:
				amount = str(amount)
			if type(amount) == str:
				if precision is None:
					if "." in amount:
						precision = len(amount) - amount.rindex(".") - 1
					else:
						precision = 0
				amount = float(amount.replace(",", ""))
			if precision is None:
				raise ValueError("precision must be specified")
			if type(amount) == float:
				amount = int(amount * (10 ** precision))
			self.symbol = asset
			self.amount = amount # int!
			self.precision = precision
			self.delim = delim
		def __float__(self):
			return self.amount / pow(10, self.precision)
		def __int__(self):
			return int(self.amount)
		def fmt(self, delim=None):
			if delim is None: delim = self.delim
			return ("{:"+delim+".{prec}f}").format(
				float(self),
				prec=self.precision
			)
		def __str__(self):
			return self.fmt() + " " + self.symbol
		def __repr__(self):
			return "<QAmount " + str(self) + ">"

	def getBalance(self, amount, asset_id, force_remote=False, force_local=False):
		if asset_id.startswith('1.3.'):
			store = self.assetStorage
			if asset_id in store.ids_to_symbols:
				sym = store.ids_to_symbols[asset_id]
			else:
				sym = None
		else:
			sym = asset_id
		b = None
		# local
		if not(force_remote):
			try:
				prec = self.minicache_precision.get(sym, None)
				if not prec or not sym:
					if not sym: sym = asset_id
					try:
						a = self.getAsset(asset_id, force_local=force_local)
						prec = int(a["precision"])
						sym = a["symbol"]
						asset_id = a["id"]
					except:
						prec = 0
						if not sym.startswith("?"):
							sym = "?" + sym
				b = self.QAmount(sym, amount, prec, delim="")
				return b
			except:
				if (force_local):
					raise
				import traceback
				traceback.print_exc()
				pass
		
		# remote
		if sym: op = {"amount":str(amount).replace(",",""), "asset": sym}
		else: op = {"amount":amount, "asset_id": asset_id}
		
		b = self.getAmountOP(op, force_local=force_local)
		return b
	
	def getBalanceOP(self, op_amount):
		if 'asset' in op_amount:
			return self.getBalance(float(op_amount['amount']), op_amount['asset'])
		return self.getBalance(int(op_amount['amount']), op_amount['asset_id'])
	
	def getAmount(self, asset_amount, asset_id, force_local=False):
		asset = self.getAsset(asset_id, force_local=force_local)
		
		#if type(asset_amount) == str:
		#	asset_amount = float(asset_amount)
		#if type(asset_amount) == float:
		#	asset_amount = int(asset_amount * 10 ** asset["precision"])
		
		if type(asset_amount) == int:
			asset_amount = int(asset_amount) / 10 ** asset["precision"]
		
		from bitshares.amount import Amount
		return Amount(asset_amount, asset, blockchain_instance=self.bts)
	
	def getAmountOP(self, op_amount, force_local=False):
		#from pprint import pprint
		#pprint(op_amount)
		if 'asset' in op_amount:
			return self.getAmount(float(op_amount['amount']), op_amount['asset'], force_local=force_local)
		return self.getAmount(int(op_amount['amount']), op_amount['asset_id'], force_local=force_local)
	
	def getBalances(self, account_name_or_id, force_local=False, force_remote=False, cache=True):
		if isinstance(account_name_or_id, str):
			account = self.getAccount(account_name_or_id)
		else:
			account = account_name_or_id
		balances = [ ]
		if hasattr(account, '_balances') and not(force_remote):
			for sym, val in account._balances.items():
				b = self.getBalance(val, sym, force_local=force_local)
				self.fave_coinnames.add(b.symbol)
				balances.append(b)
			return balances
		
		if force_local:
			return balances
		
		rpc = self.bts.rpc
		op_balances = rpc.get_account_balances(account["id"], [])
		for op_amount in op_balances:
			b = self.getBalanceOP(op_amount)
			self.fave_coinnames.add(b.symbol)
			balances.append(b)
		
		if cache:
			blnc = { }
			for b in balances:
				blnc[b.symbol] = str(b).split(" ")[0]
			self.storeBalances(account["name"], blnc)
		
		return balances
	
	def getMemo(self, from_account, to_account, text=None, data=None):
		if (data):
			from_account = data["from"]
			to_account = data["to"]
			#data = data["message"]
		
		#import traceback
		#try:
		#	from_account = self.getAccount(from_account)
		#except:
		#	traceback.print_exc()
		#	#print(from_account
		#	#print(from_account)
		try:
			to_account = self.getAccount(to_account)
			to_account_name = to_account["name"]
		except:
			to_account_name = to_account
			to_account = None
		#invert = True
		
		#to_account = self.getAccount(to_account)
		try:
			from_account = self.getAccount(from_account)
			from_account_name = from_account["name"]
		except:
			from_account_name = from_account
			from_account = None
		
		#print("TO:", to_account)
		#print("FROM:", from_account)
		#if (self.isCachedAccount(to_account['name'])):
		#	invert = False
		#else:
		#	if not(from_account):
		#		showerror(from_account_name)
		#		return False
		
		from bitshares.memo import Memo
		memoObj = Memo(
			from_account=None,#from_account,
			to_account=None,#to_account,
			blockchain_instance=self.bts
		)
		memoObj.chain_prefix = self.chain_prefix()
		memoObj.from_account = from_account
		memoObj.to_account = to_account
		if text:
			# { nonce, to from, message } json:
			return memoObj.encrypt(text)
		# plaintext:
		return {
			'message': memoObj.decrypt(data),
			'from': from_account_name, #from_account['name']
			'to': to_account_name, #to_account['name'],
		}
	
	
	def matchBlindOutputs(self, outputs, txt2=""):
		iso = self
		store = iso.store.blindStorage
		
		#txt2 = h["description"]
		text = ""
		n = 0
		for out in outputs:#op["outputs"]:
			commitment = out["commitment"]
			balance = store.getEntry(commitment)
			if not balance:
				continue
			#data = json.loads(balance["graphene_json"])
			text += "Commitment " + out["commitment"]
			text += "\n " + balance["description"]
			text += "\n Receipt: " + balance["receipt"]
			text += "\n\n"
			n += 1
			txt2 += "\n" + balance["receipt"]
		
		return (n, text, txt2)
	
	def downloadOrders(self, account):
		return account.openorders()
		#from .price import Order
		#return [Order(o, blockchain_instance=self.bitshares) for o in self["limit_orders"]]
	
	
	def softAccountName(self, account_id, remote=True):
		if not(account_id.startswith("1.2.")):
			return account_id # already a perfect name
		cache = self.minicache_accnames
		if account_id in cache:
			return cache[account_id]
		try:
			account = self.getAccount(account_id, force_remote=remote)
		except:
			account = None
		if account:
			cache[account_id] = account["name"]
			return account["name"]
		return account_id
	
	def softAmountStr(self, asset_amount, asset_id, delim=""):
		precision = self.minicache_precision.get(asset_id, 0)
		return self.QAmount(asset_id, asset_amount, precision, delim).fmt()
		#if not(type(asset_amount) == int):
		#	t = str(asset_amount)
		#	if not("e" in t):
		#		return t # perfect as is
		if type(asset_amount) == int:
			asset_amount = int(asset_amount) / 10 ** precision
		if not(type(asset_amount) == float):
			asset_amount = float(asset_amount)
		return ("{:"+delim+".{p}f}").format(asset_amount, p=precision)
		return ("%0."+str(int(math.log10(precision)))+"f") % amount
	
	def bootstrap_wallet(self, wipe=False):
		import bitsharesqt.bootstrap as bootstrap
		store = self.store.remotesStorage
		if wipe:
			store.wipe()
		
		for n in bootstrap.KnownFaucets:
			store.add(2, n[0], n[1], n[2], n[3].__name__)
		
		for n in bootstrap.KnownTraders:
			store.add(1, n[0], n[1], n[2], n[3].__name__)
		
		for n in bootstrap.KnownNodes:
			store.add(0, n[0], n[1], n[2], "")
	
	def historyDescription(iso, h, account=None):
		accname = iso.softAccountName
		#from pprint import pprint
		#pprint(h)
		
		op_id, op_action = h['op']
		res_id, op_result = h['result']
		
		desc = "Some operation"
		plus = ""
		minus = ""
		short = ""
		from bitsharesbase.operations import getOperationNameForId
		icon = getOperationNameForId(op_id).lower()
		if (op_id == 0):
			desc = "Transfer"
			#from_account = iso.getAccount(op_action['from'])
			#to_account = iso.getAccount(op_action['to'])
			amt = iso.getAmountOP(op_action['amount'])
			desc += " from " + accname(op_action['from']) #from_account['name']
			desc += " to " + accname(op_action['to']) #to_account['name']
			desc += " - " + str(amt)
			if account and account["id"] == op_action["from"]:
				short = "Transfered to " + accname(op_action['to'])
				minus = str(amt)
				icon = "transfer_to"
			if account and account["id"] == op_action["to"]:
				short = "Transfered from " + accname(op_action['from'])
				plus = str(amt)
				icon = "transfer_from"
		if (op_id == 1):
			desc = "Place order"
			amt_a = iso.getAmountOP(op_action['amount_to_sell'])
			amt_b = iso.getAmountOP(op_action['min_to_receive'])
			desc += " for "
			desc += str(amt_b)
			desc += " paying "
			desc += str(amt_a)
			short = "Placed order for " + str(amt_b) + " paying " + str(amt_a)
		if (op_id == 2):
			desc = "Cancel order"
			short = "Canceled order"
		if (op_id == 3):
			desc = "Borrow"
			amt_a = iso.getAmountOP(op_action['delta_debt'])
			amt_b = iso.getAmountOP(op_action['delta_collateral'])
			desc += " - " + str(amt_a) + " for "
			desc += str(amt_b)
			short = "Borrowed"
			plus = str(amt_b)
			minus = str(amt_a)
		if (op_id == 4):
			desc = "Trade"
			#who = Account(op_action['account_id'])
			amt_a = iso.getAmountOP(op_action['pays'])
			amt_b = iso.getAmountOP(op_action['receives'])
			desc += " - " + str(amt_a) + " for "
			desc += str(amt_b)
			short = "Traded"
			plus = str(amt_b)
			minus = str(amt_a)
		if (op_id == 5):
			desc = "Register account"
			#reg_account = iso.getAccount(op_action['registrar'])
			#dst_account = iso.getAccount(op_action['name'])
			desc += " by " + accname(op_action['registrar']) #reg_account['name']
			desc += " - " + accname(op_action['name']) #self.softAccountName(#dst_account['name']
			short = "Registered account " + accname(op_action['name'])
		if (op_id == 8):
			desc = "Upgrade account"
			#dst_account = iso.getAccount(op_action['account_to_upgrade'])
			desc += " - " + accname(op_action['account_to_upgrade']) #self.softAccountName(#dst_account['name']
			short = "Upgraded account " + accname(op_action['account_to_upgrade'])
		if (op_id == 6):
			desc = "Update account/votes"
			#dst_account = iso.getAccount(op_action['account'])
			if "owner_key" in op_action:
				desc = "Sweep owner key"
				icon = "account_update_key"
			if "active_key" in op_action:
				icon = "account_update_key"
				if "owner_key" in op_action:
					desc = "Sweep owner and active keys"
				else:
					desc = "Sweep active key"
			desc += " - " + accname(op_action['account']) #self.softAccountName(#dst_account['name']

		if (op_id == 10):
			desc = "Create asset"
			try:
				reg_asset = iso.getAsset(op_action['symbol'])
			except:
				pass
			#reg_account = iso.getAccount(op_action['issuer'])
			desc += " by " + accname(op_action["issuer"]) #reg_account['name']
			desc += " - " + op_action["symbol"].upper() #reg_asset["symbol"]
		if (op_id == 11):
			desc = "Update asset"
			try:
				reg_asset = iso.getAsset(op_action['asset_to_update'])
				desc += " - " + reg_asset["symbol"]
			except:
				pass
		if (op_id == 12):
			desc = "Update bitasset"
			try:
				reg_asset = iso.getAsset(op_action['asset_to_update'])
				desc += " - " + reg_asset["symbol"]
			except:
				pass
		if (op_id == 13):
			desc = "Update feed producers"
			try:
				reg_asset = iso.getAsset(op_action['asset_to_update'])
				desc += " - " + reg_asset["symbol"]
			except:
				pass
		if (op_id == 14):
			desc = "Issue"
#			is_asset = iso.getAsset(op_action['asset_to_issue']['asset_id'])
			amt = iso.getAmountOP(op_action['asset_to_issue'])
			desc += " by " + accname(op_action["issuer"])
			desc += " to " + accname(op_action["issue_to_account"])
			desc += " - " + str(amt)
			if account and account["id"] == op_action["issue_to_account"]:
				short = "Issued from " + accname(op_action['issuer'])
				plus = str(amt)
				icon = "transfer_from"
			if account and account["id"] == op_action["issuer"]:
				short = "Issued to " + accname(op_action['issue_to_account'])
				minus = str(amt)
				icon = "transfer_to"
		if (op_id == 15):
			desc = "Reserve"
			amt = iso.getAmountOP(op_action['amount_to_reserve'])
			desc += " by " + accname(op_action["payer"])
			desc += " - " + str(amt)
			minus = str(amt)
			try:
				is_asset = iso.getAsset(op_action['amount_to_reserve']['asset_id'])
				if is_asset["issuer"] == op_action["payer"]:
					plus = str(amt)
			except:
				pass
			short = "Reserved by " + accname(op_action["payer"]) + " - " + str(amt)
		if (op_id == 16):
			desc = "Fund fee pool"
			try:
#				f_asset = iso.getAsset(op_action['asset_id'])
#				amt = iso.QAmount(f_asset["symbol"], op_action['amount'], precision=f_asset["precision"])
				f_asset = iso.getAsset(op_action['asset_id'])
				amt = iso.QAmount("BTS", op_action['amount'], precision=5)
				desc += " for " + f_asset["symbol"]
				desc += " - " + str(amt)
				short = "Funded fee pool for " + f_asset["symbol"]
				minus = str(amt)
			except:
				pass
		if (op_id == 17):
			desc = "Settle"
			amt = iso.getAmountOP(op_action['amount'])
			desc += " " + str(amt)
			short = "Settled"
			minus = str(amt)
			try:
				get_amt = iso.getAmountOP(op_result)
				plus = str(get_amt)
			except:
				pass
		if (op_id == 18):
			desc = "Global settle"
			try:
				from bitshares.price import Price
				p = Price(op_action["settle_price"], blockchain_instance=iso.bts)
				stl_asset = iso.getAsset(op_action['asset_to_settle'])
				desc += " " + stl_asset["symbol"]
				desc += " at " + str(p)
			except:
				pass

		if (op_id == 19):
			desc = "Publish feed for asset"
			try:
				f_asset = iso.getAsset(op_action['asset_id'])
				desc += " " + f_asset["symbol"]
				short = "Published feed for " + f_asset["symbol"]
			except:
				short = "Published feed for asset"

		if (op_id == 34):
			desc = "Create worker '%s'" % op_action['name']
			short = "Created worker '%s'" % op_action['name']

		if (op_id == 38):
			desc = "Sieze"
			amt = iso.getAmountOP(op_action['amount'])
			desc += " from " + accname(op_action['from'])
			desc += " to " + accname(op_action['to'])
			desc += " - " + str(amt)
			if account and account["id"] == op_action["from"]:
				short = "Siezed to " + accname(op_action['to'])
				minus = str(amt)
				icon = "transfer_to"
			if account and account["id"] == op_action["to"]:
				short = "Siezed from " + accname(op_action['from'])
				plus = str(amt)
				icon = "transfer_from"
		if (op_id == 39):
			desc = "Transfer to blind"
			amt = iso.getAmountOP(op_action['amount'])
			desc += " - " + str(amt)
			short = "Transfered to blind"
			minus = str(amt)
		if (op_id == 40):
			desc = "Blind transfer"
#			amt = iso.getAmountOP(op_action['amount'])
#			desc += " - " + str(amt)
			short = "Blind transfer"
#			minus = str(amt)
		if (op_id == 41):
			desc = "Transfer from blind"
			desc += " to " + accname(op_action['to']) #reg_account['name']
			amt = iso.getAmountOP(op_action['amount'])
			desc += " - " + str(amt)
			short = "Transfered from blind"
			#short += " to " + accname(op_action['to']) #reg_account['name']
			plus = str(amt)
		
		if (op_id == 43):
			desc = "Claim market fees"
			amt = iso.getAmountOP(op_action['amount_to_claim'])
			desc += " " + str(amt)
			short = "Claimed market fees"
			plus = str(amt)
		if (op_id == 47):
			desc = "Claim from fee pool"
			amt = iso.getAmountOP(op_action['amount_to_claim'])
			desc += " " + str(amt)
			short = "Claimed from fee pool"
			plus = str(amt)
		if (op_id == 48):
			desc = "Change ownership"
			try:
				up_asset = iso.getAsset(op_action['asset_to_update'])
				desc += " for " + up_asset["symbol"]
			except:
				up_asset = None
				pass
			desc += " to " + accname(op_action['new_issuer'])
			if account and account["id"] == op_action['new_issuer']:
				short = "Obtained ownership"
				if up_asset:
					short += " over " + up_asset["symbol"]
				short += " from " + accname(op_action['issuer'])
			else:
				short = desc.replace("Change ownership", "Changed ownership")
		
		return {
			"long": desc,
			"short": short,
			"plus": plus,
			"minus": minus,
			"icon": icon,
		}
	
	class WalletGate(object):
		def __init__(self, wallet, mainwin, reason=None, parent=None):
			self.wallet = wallet
			self.reason = reason
			self.parent = parent
			self.relock = wallet.locked()
			self.mainwin = mainwin
		def __enter__(self):
			if self.relock:
				unlocked = self.mainwin.unlock_wallet(reason=self.reason, parent=self.parent)
				if not unlocked:
					raise WalletLocked()
			return self.wallet
		def __exit__(self, exc_type, exc_val, exc_tb):
			from .utils import app
			if self.relock:
				self.mainwin.lock_wallet()
	def unlockedWallet(self, parent=None, reason=None):
		return self.WalletGate( self.bts.wallet, self.mainwin, reason, parent )
	
	
	def download_assets(self, request_handler=None):
		rh = request_handler
		store = self.store.assetStorage
		save = [ ]
		rpc = self.bts.rpc
		
		lower_bound_symbol = ""
		limit = 100
		
		done = False
		while not done:
			if rh and rh.cancelled:
				raise Cancelled()
			if self.offline:
				raise ResourceUnavailableOffline("Asset batch")
			batch = rpc.list_assets(lower_bound_symbol, limit)
			dynamic_ids = [ ]
			bitasset_ids = [ ]
			bitasset_assets = [ ]
			for asset in batch:
				if "bitasset_data_id" in asset and asset["bitasset_data_id"]:
				#	asset["bitasset_data"] = rpc.get_object(asset["bitasset_data_id"])
					bitasset_ids.append(asset["bitasset_data_id"])
					bitasset_assets.append(asset)
				#asset["dynamic_asset_data"] = rpc.get_object(asset["dynamic_asset_data_id"])
				dynamic_ids.append(asset["dynamic_asset_data_id"])
			if len(bitasset_ids) > 0:
				bit_data = rpc.get_objects(bitasset_ids)
				j = -1
				for reply in bit_data:
					j += 1
					bitasset_assets[j]["bitasset_data"] = reply
			dyn_data = rpc.get_objects(dynamic_ids)
			j = -1
			for reply in dyn_data:
				j += 1
				batch[j]["dynamic_asset_data"] = reply
			for asset in batch:
				self.saveAsset(asset)
				#save.append(asset)
			if len(batch) < limit:
				break
			last = batch[-1]
			lower_bound_symbol = last['symbol']
		return save

	def download_asset(self, symbol):
		rpc = self.bts.rpc
		
		asset = rpc.get_asset(symbol)
		if "bitasset_data_id" in asset and asset["bitasset_data_id"]:
			asset["bitasset_data"] = rpc.get_object(asset["bitasset_data_id"])
		asset["dynamic_asset_data"] = rpc.get_object(asset["dynamic_asset_data_id"])
		
		self.saveAsset(asset)
		
		return asset
	
	def _marketMatrix(self):
		return [ ]
		tags = set(self.fave_markets)
		for a in self.fave_coinnames:
			for b in self.fave_coinnames:
				if a == b:
					continue
				tag = a + ":" + b
				retag = b + ":" + a
				if tag in tags or retag in tags:
					continue
				tags.add(tag)
		return tags
	
	def _flipFaveMarket(self, tag):
		a, b = str.split(tag, ":")
		retag = b + ":" + a
		if tag in self.fave_markets:
			self.fave_markets.remove(tag)
		self.fave_markets.add(retag)
	
	def download_topmarkets(self, request_handler=None):
		rh = request_handler
		rpc = self.bts.rpc

		total = 25
		cnt = 0

		mrs = rpc.get_top_markets(25)
		markets = [ ]
		for mr in mrs:
			cnt += 1
			if rh and rh.cancelled:
				raise Cancelled()
			name = mr['base']+":"+mr['quote']
			ticker = { "percent_change": 0., "latest": 0. }
			ticker = rpc.get_ticker(mr['base'], mr['quote'])
			vol = { "base": mr['base'],
				"quote": mr['quote'],
				"base_volume": mr['base_volume'],
				"quote_volume": mr['quote_volume']
				 }
			markets.append( (name, ticker, vol) )
			prog = int(cnt / total * 100)
			rh.ping(prog, None)
#		ticker = rpc.get_ticker(a, b)
		return markets

	def download_markets(self, names, request_handler=None):
		if names is None:
			return self.download_topmarkets(request_handler=request_handler)
			names = self._marketMatrix()
		rpc = self.bts.rpc
		markets = [ ]
		for name in names:
			markets.append( self.download_market(name) )
		return markets
	
	def download_market(self, name):
		if self.offline:
			raise ResourceUnavailableOffline("Market " + name)
		rpc = self.bts.rpc
		
		a, b = str.split(name,":")
		ticker = rpc.get_ticker(a, b)
		vol = rpc.get_24_volume(a, b)
		return (name, ticker, vol)
	
	# this must be called from threads only!
	def _wait_online(self,timeout=3):
		import time
		while not(self.is_connected()):
			if timeout <= 0:
				raise TimeOut()
			timeout -= 1
			time.sleep(1)
	
	def voteInfo(self, object_id, ref="vote_for"):
		if object_id.startswith("1.6."):
			t = "witness"
			ref = "vote_id"
		elif object_id.startswith("1.5."):
			t = "committee_member"
			ref = "vote_id"
		elif object_id.startswith("1.14."):
			t = "worker"
		else:
			raise ValueError("Wrong object id in %s." % ref)
		obj = self.bts.rpc.get_object(object_id)
		if not obj:
			raise ValueError("Object %s not found on the chain." % object_id)
		return {
			"type": t,
			"object_id": object_id,
			"vote_id": obj[ref]
		}


	def getWitnesses(self, only_active=False, lazy=False, request_handler=None):
#		from bitshares.witness import Witnesses
#		return Witnesses(blockchain_instance=self.bts, lazy=lazy)
		rh = request_handler
		from bitshares.account import Account
		ids = self.bts.rpc.get_object(
			"2.12.0").get("current_shuffled_witnesses", [])
		witnesses = [ ]
		seq, size = list(ids), 100
		sub_lists = [seq[i:i+size] for i in range(0, len(seq), size)]
		for ids in sub_lists:
			if rh and rh.cancelled:
				raise Cancelled()
			data = self.bts.rpc.get_objects(ids)
			for wit in data:
				witnesses.append(wit)

		from bitshares.witness import Witness
		accs = set()
		accmaps = { }
		ret = [ ]
		for w in witnesses:
			if rh and rh.cancelled:
				raise Cancelled()
			wit = Witness(w, lazy=lazy, blockchain_instance=self.bts)
			if not wit["witness_account"] in accs:
				accs.add(wit["witness_account"])
				accmaps[wit["witness_account"]] = [ ]
			accmaps[wit["witness_account"]].append(wit)
			ret.append(wit)
		seq, size = list(accs), 100
		sub_lists = [seq[i:i+size] for i in range(0, len(seq), size)]
		for idlist in sub_lists:
			if rh and rh.cancelled:
				raise Cancelled()
			data = self.bts.rpc.get_objects(idlist)
			for acc in data:
				for wit in accmaps[acc["id"]]:
					wit._account = acc

		if only_active:
			account = Account(
				"witness-account",
				blockchain_instance=self.bts)
			filter_by = [x[0] for x in account["active"]["account_auths"]]
			ret = list(
				filter(lambda x: x["witness_account"] in filter_by,
				ret))

		return ret
	
	def getCommittee(self, only_active=False, lazy=False, request_handler=None):
		rh = request_handler
		from bitshares.committee import Committee
		rpc = self.bts.rpc
		ids = [ ]
		last_name = ""
		while True:
			if rh and rh.cancelled:
				raise Cancelled()
			refs = rpc.lookup_committee_member_accounts(last_name, 100)
			last_name = refs[-1][0]
			for name, identifier in refs:
				ids.append(identifier)
			if len(refs) < 100:
				break

		accs = set()
		accmaps = { }
		ret = [ ]

		seq, size = list(ids), 100
		sub_lists = [seq[i:i+size] for i in range(0, len(seq), size)]
		for ids in sub_lists:
			if rh and rh.cancelled:
				raise Cancelled()
			data = self.bts.rpc.get_objects(ids)
			for cm in data:
				mem = Committee(cm, lazy=lazy, blockchain_instance=self.bts)
				if not mem["committee_member_account"] in accs:
					accs.add(mem["committee_member_account"])
					accmaps[mem["committee_member_account"]] = [ ]
				accmaps[mem["committee_member_account"]].append(mem)
				ret.append(mem)

		seq, size = list(accs), 100
		sub_lists = [seq[i:i+size] for i in range(0, len(seq), size)]
		for idlist in sub_lists:
			if rh and rh.cancelled:
				raise Cancelled()
			data = self.bts.rpc.get_objects(idlist)
			for acc in data:
				for mem in accmaps[acc["id"]]:
					mem._account = acc

		return ret
	
	def getWorkers(self, only_active=False, lazy=False, request_handler=None):
		#from bitshares.worker import Workers
		#return Workers(blockchain_instance=self.bts, lazy=lazy)
		rh = request_handler
		from bitshares.worker import Worker
		workers = self.bts.rpc.get_all_workers()
		accs = set()
		accmaps = { }
		ret = [ ]
		for w in workers:
			wrk = Worker(w, lazy=lazy, blockchain_instance=self.bts)
			if not wrk["worker_account"] in accs:
				accs.add(wrk["worker_account"])
				accmaps[wrk["worker_account"]] = [ ]
			accmaps[wrk["worker_account"]].append(wrk)
			ret.append(wrk)
		seq, size = list(accs), 100
		sub_lists = [seq[i:i+size] for i in range(0, len(seq), size)]
		for idlist in sub_lists:
			if rh and rh.cancelled:
				raise Cancelled()
			data = self.bts.rpc.get_objects(idlist)
			for acc in data:
				for wrk in accmaps[acc["id"]]:
					wrk._account = acc
		return ret
	
	def getMarketBuckets(self, asset_a, asset_b, start=None, stop=None, raw=False):
		from datetime import datetime, timedelta
		from bitshares.utils import formatTime
		if not stop: stop = datetime.now()
		if not start: start = stop - timedelta(hours=24)
		interval = (stop - start).total_seconds()
		bucket_len = interval / 200
		bucket_sizes = self.bts.rpc.market_buckets
		actual_bucket_len = bucket_sizes[-1]#60
		#for b in bucket_sizes:
		#	if bucket_len >= b:
		#		actual_bucket_len = b
		for b in reversed(bucket_sizes):
			if bucket_len <= b:
				actual_bucket_len = b
		#stop = stop + timedelta(seconds=actual_bucket_len)
		buckets = self.bts.rpc.get_market_history(
			asset_a["id"],
			asset_b["id"],
			int(actual_bucket_len),
			formatTime(start),
			formatTime(stop),
			api="history",
		)
		if raw:
			return buckets
		trades = [ ]
		for o in buckets:
			prec1 = self.softAmountStr(int(o["close_base"]), asset_a["symbol"], delim="")
			prec2 = self.softAmountStr(int(o["close_quote"]), asset_b["symbol"], delim="")
			price = float(prec1) / float(prec2)
			t = { "date": o["key"]["open"], "price": price }
			trades.append(t)
		return trades
	

from .utils import showexc, num_args
from .work import has_kwarg
def safeunlock(func, reason=None):
	def wrapper(obj, *args, **kwargs):
		try:
			args = list(args) #list(args[0:num_args(func)])
			with obj.iso.unlockedWallet(obj, reason) as w:
				if has_kwarg(func, "wallet"):
					kwargs["wallet"] = w
				else:
					args[-1] = w
				return func(obj, *args, **kwargs)
		except WalletLocked:
			pass
		except Exception as e:
			showexc(e)
	return wrapper
