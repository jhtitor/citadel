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
		
		self.ping_callback = kwargs.pop("ping_callback", None)
		
		self.conn_node = kwargs.pop('node', "")
		self.conn_rpcuser = kwargs.pop('rpcuser', "")
		self.conn_rpcpassword = kwargs.pop('rpcpassword', "")
		
		#self.bts = lambda: 0 #bitshares.BitShares(*args, offline=True, **kwargs)
		self.bts = bitshares.BitShares(*args, offline=True, wallet=None, store=None, **kwargs)
		self.bts.rpc = None
		self.store = None
		self.offline = True
		
		self.subscribed_accounts = set()
		self.subscribed_markets = set()
		
		self.minicache_accnames = {} # 1.2.ID to name
		self.fave_coinnames = set() # semi-random
		self.fave_markets = set() # same
		
		#from bitsharesapi.bitsharesnoderpc import BitSharesNodeRPC
	
	def disconnect(self):
		return self.close()
		
	def close(self, force=False):
		if self.offline and not(force):
			return True
		
		try:
			if self.bts.rpc:
				self.bts.rpc.close()
		except:
			pass
		try:
			self.bts.rpc.ws.close()
		except:
			pass
		self.bts.rpc = None
		self.offline = True
		
	def connect(self, *args, **kwargs):
		if not self.offline:
			return True
		
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
		proxyHost = config.get('proxy_host', None)
		proxyPort = config.get('proxy_port', 9150)
		proxyType = config.get('proxy_type', "socks5")
		proxyUrl = None
		if proxyOn and proxyHost:
			proxyUrl = str(proxyType) + "://" + str(proxyHost) + ":" + str(proxyPort)
		
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
	
	def injectBalance(self, account_id, asset_symbol, amount):
		iso = self
		store = self.store.accountStorage
		account = self.getAccount(account_id, force_remote=False)
		asset = self.getAsset(asset_symbol)
		value = int(amount) / pow(10, asset["precision"])
		acc_blnc = iso.getBalances(account["id"])
		blnc = { }
		for o in acc_blnc:
			blnc[o.symbol] = o.amount
		blnc[asset_symbol] = value
		#print("Post-inject", blnc)
		self.storeBalances(account["name"], blnc)
		account._balances = blnc
		return account
	
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
		names = set()
		accountStorage = self.store.accountStorage
		accs = accountStorage.getAccounts()
		return list(accs)
		#print("GOT AcCS from Storage")
		#pprint(accs)
		for acc in accs:
			#pprint(acc)
			if acc is None: #?!?!??!
				continue
			#if acc['name']:
				names.add(acc)#acc['name'])
		return list(names)
	
	def _accountFromDict(self, account_id, accountInfo):
		from bitshares.account import Account
		
		account = Account.__new__(Account)
		account.identifier = account_id
		account.bitshares = self.bts
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
			
			return account
		
		account = self._accountFromDict(account_id, accountInfo)
		
		return account
	
	def getAsset(self, asset_id, cache=True, force_remote=False):
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
			forged_asset.bitshares = self.bts
			forged_asset.cached = True
			forged_asset.lazy = True
			forged_asset.full = False
			forged_asset.asset = stored_asset["symbol"]
			for k, v in stored_asset.items():
				forged_asset[k] = v
			return forged_asset
		
		if self.offline:
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
	
	def storeAccount(self, account):
		iso = self
		accountStore = iso.accountStorage
		jsond =  { }
		for key, val in account.items():
			jsond[key] = val
		
		if "balances" in jsond:
			jsond.pop("balances")
		
		blnc = { }
		for amount in self.getBalances(account['id'], force_local = True):#.balances:
			blnc[str(amount.symbol)] = float(amount)
		
		try:
			accountStore.add(account['name'], account['id'])
		except ValueError: # already exists
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
	
	def getAmount(self, asset_amount, asset_id):
		asset = self.getAsset(asset_id)
		
		#if type(asset_amount) == str:
		#	asset_amount = float(asset_amount)
		#if type(asset_amount) == float:
		#	asset_amount = int(asset_amount * 10 ** asset["precision"])
		
		if type(asset_amount) == int:
			asset_amount = int(asset_amount) / 10 ** asset["precision"]
		
		from bitshares.amount import Amount
		return Amount(asset_amount, asset, blockchain_instance=self.bts)
	
	def getAmountOP(self, op_amount):
		#from pprint import pprint
		#pprint(op_amount)
		if 'asset' in op_amount:
			return self.getAmount(float(op_amount['amount']), op_amount['asset'])
		return self.getAmount(int(op_amount['amount']), op_amount['asset_id'])
	
	def getBalances(self, account_name_or_id, force_local=False, force_remote=False, cache=True):
		account = self.getAccount(account_name_or_id)
		balances = [ ]
		if hasattr(account, '_balances') and not(force_remote):
			for sym,val in account._balances.items():
				try:
					b = self.getAmountOP({"amount":val, "asset": sym})
				except:
					b = lambda: None
					b.symbol = sym
					b.amount = val
				self.fave_coinnames.add(sym)
				balances.append( b ) #Amount(val, sym, blockchain_instance=self.iso.bts) )
			return balances
		
		if force_local:
			return balances
		
		rpc = self.bts.rpc
		op_balances = rpc.get_account_balances(account["id"], [])
		for op_amount in op_balances:
			b = self.getAmountOP(op_amount)
			self.fave_coinnames.add(b.symbol)
			balances.append(b)
		
		if cache:
			blnc = { }
			for b in balances:
				blnc[b.symbol] = b.amount
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
	
	def bootstrap_wallet(self, wipe=False):
		import bitsharesqt.bootstrap as bootstrap
		store = self.store.remotesStorage
		if wipe:
			store.wipe()
		for n in bootstrap.KnownFaucets:
			store.add(2, n[0], n[1], n[2])
		
		for n in bootstrap.KnownTraders:
			store.add(1, n[0], n[1], n[2])
		
		for n in bootstrap.KnownNodes:
			store.add(0, n[0], n[1], n[2])
	
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
		if (op_id == 2):
			desc = "Cancel order"
		if (op_id == 4):
			desc = "Traded"
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
		if (op_id == 8):
			desc = "Upgrade account"
			#dst_account = iso.getAccount(op_action['account_to_upgrade'])
			desc += " - " + accname(op_action['account_to_upgrade']) #self.softAccountName(#dst_account['name']
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
		if (op_id == 14):
			desc = "Issue"
			is_asset = iso.getAsset(op_action['asset_to_issue']['asset_id'])
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
			desc = "Reserved"
			is_asset = iso.getAsset(op_action['amount_to_reserve']['asset_id'])
			amt = iso.getAmountOP(op_action['amount_to_reserve'])
			desc += " by " + accname(op_action["payer"])
			desc += " - " + str(amt)
			minus = str(amt)
			if is_asset["issuer"] == op_action["payer"]:
				plus = str(amt)
			short = "Reserved by " + accname(op_action["payer"]) + " - " + str(amt)
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
		
		return {
			"long": desc,
			"short": short,
			"plus": plus,
			"minus": minus,
			"icon": icon,
		}
	
	class WalletGate(object):
		def __init__(self, wallet):
			self.wallet = wallet
			self.relock = wallet.locked()
		def __enter__(self):
			from .utils import app
			if self.relock:
				unlocked = app().mainwin.unlock_wallet()
				if not unlocked:
					raise WalletLocked()
			return self.wallet
		def __exit__(self,exc_type, exc_val, exc_tb):
			from .utils import app
			if self.relock:
				app().mainwin.lock_wallet()
	def unlockedWallet(self):
		return self.WalletGate( self.bts.wallet )
	
	
	def download_assets(self):
		store = self.store.assetStorage
		rpc = self.bts.rpc
		
		lower_bound_symbol = ""
		limit = 100
		
		done = False
		while not done:
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
			if len(batch) < limit:
				break
			last = batch[-1]
			lower_bound_symbol = last['symbol']
	
	def download_asset(self, symbol):
		rpc = self.bts.rpc
		
		try:
			asset = rpc.get_asset(symbol)
			if "bitasset_data_id" in asset and asset["bitasset_data_id"]:
				asset["bitasset_data"] = rpc.get_object(asset["bitasset_data_id"])
			asset["dynamic_asset_data"] = rpc.get_object(asset["dynamic_asset_data_id"])
		except:
			asset = None
		if not asset:
			return None
		
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
	
	def download_markets(self, names):
		if names is None:
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
	