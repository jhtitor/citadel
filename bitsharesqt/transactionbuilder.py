from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.transactionbuilder import Ui_QTransactionBuilder

from PyQt5.QtWidgets import QTableWidgetItem

from .utils import *
import logging
log = logging.getLogger(__name__)

#from bitshares import BitShares
from bitshares.account import Account
from bitshares.amount import Amount
from bitsharesbase.account import PasswordKey
from bitsharesbase.account import PrivateKey
from bitsharesbase.account import BrainKey

from bitshares.transactionbuilder import TransactionBuilder
from bitsharesbase.operations import Transfer
from bitsharesbase.operations import Transfer_to_blind
from bitsharesbase.operations import Limit_order_create, Limit_order_cancel
from bitsharesbase.operations import Asset_settle
from bitsharesbase.operations import Account_create, Account_upgrade, Account_update
from bitsharesbase.operations import Asset_create, Asset_update, Asset_update_bitasset
from bitsharesbase.operations import Asset_update_issuer
from bitsharesbase.operations import Asset_update_feed_producers, Asset_publish_feed
from bitsharesbase.operations import Asset_issue, Asset_reserve, Override_transfer
from bitsharesbase.operations import Asset_fund_fee_pool, Asset_claim_pool, Asset_claim_fees
from bitsharesbase.operations import Asset_global_settle
from bitsharesbase.operations import Worker_create
from bitsharesbase.operations import getOperationIdForClass
from bitsharesbase.operations import getOperationClassForId
from bitsharesbase.operations import getOperationNameForId
from bitsharesbase.asset_permissions import toint
from graphenebase.objects import GrapheneObject

import json

class QTransactionBuilder(QtWidgets.QDialog):
	def __init__(self, *args, trxbuffer, iso, **kwargs):
		super(QTransactionBuilder, self).__init__(*args,**kwargs)
		self.ui = ui = Ui_QTransactionBuilder()
		self.ui.setupUi(self)
		
		#trxbuffer.addSigning
		self.applyTransaction(trxbuffer, iso)
		
		self.tx = trxbuffer
		self.iso = iso
		self.ui.signButton.clicked.connect(self.sign_transaction)
		self.ui.broadcastButton.clicked.connect(self.broadcast_transaction)
		
		stretch_tree(self.ui.treeWidget)
		stretch_table(self.ui.signatureTable)
		
		self.ui.importButton.clicked.connect(self.import_transaction)
		self.ui.exportButton.clicked.connect(self.export_transaction)
	
	def setPreviewMode(self, on):
		if on:
			self.ui.signButton.setVisible(False)
			self.ui.broadcastButton.setVisible(False)
			self.ui.importButton.setEnabled(False)
			#self.ui.exportButton.set
	
	def highlightOp(self, ind):
		table = self.ui.treeWidget
		num = table.topLevelItemCount()
		if num < 2:
			return
		item = table.topLevelItem(ind)
		brush = QtGui.QColor(COLOR_GREEN)
		item.setBackground(0, brush)
		item.setBackground(1, brush)
	
	def export_transaction(self):
		path, _ = QtGui.QFileDialog.getSaveFileName(self, 'Export transaction', '', "bitshares transaction (*.json)")
		if not path:
			return False
		
		data = self.tx.json()
		if not("operations" in data):
			data["operations"] = [ ]
			for op in self.tx.ops:
				op_id = getOperationIdForClass(op.__class__.__name__)
				op_json = op.json()
				data["operations"].append([ op_id, op_json ])
		for k in ["missing_signatures", "signatures"]:
			try:
				if not(k in data):
					data[k] = self.tx[k]
			except:
				pass
		
		data = json.dumps(data)
		
		with open(path, "w") as f:
			f.write(data)
		
		return True
	
	def import_transaction(self):
		path, _ = QtGui.QFileDialog.getOpenFileName(self, 'Import transaction file', '', "bitshares transaction (*.json)")
		if not path:
			return False
		
		with open(path, "r") as f:
			data = f.read()
		
		trx = json.loads(data)
		trx["operations"] = [
			getOperationClassForId(op_id)(**op)
			for (op_id, op) in trx["operations"]
		]
		
		tx = TransactionBuilder(trx, blockchain_instance=self.iso.bts)
		self.tx = tx
		self.applyTransaction(tx, self.iso)
		
		return True
	
	def broadcast_transaction(self):
		if not askyesno("Broadcast this transaction on the network?"):
			return
		
		tx = self.tx
		try:
			tx.broadcast()
		except Exception as e:
			showexc(e)
			return
			
		
		self.accept()
	
	def sign_transaction(self):
		tx = self.tx
		
		try:
			self.append_wifs()
			tx.sign()
			tx.pop("missing_signatures", None)
		except Exception as e:
			showexc(e)
			return
		
		self.applyTransaction(tx, self.iso)
	
	def append_wifs(self):
		tx = self.tx
		miss = tx.get("missing_signatures", [ ])
		with self.iso.unlockedWallet(self, "Sign Transaction") as w:
			for sig in miss:
				try:
					tx.appendWif( w.getPrivateKeyForPublicKey(sig) )
				except Exception as e:
					showexc(e)
	
	def applyTransaction(self, trx, iso):
		# NOTE: we must be very careful when asking trx[key],
		# the _get() method there is trigger-happy to call
		# constructTx() and loose our progress.
		root = self.ui.treeWidget
		
		core_fee = 0
		other_fees = { }
		
		root.clear()
		for op in trx.ops:
			op_id = getOperationIdForClass(op.__class__.__name__)
			op_json = op.json()
			fake_obj = {
				'op': [op_id, op_json],
				'result': [0, True]
			}
			if 'fee' in op_json:
				fee = op_json['fee']
				fee_asset_id = fee['asset_id']
				if fee_asset_id == '1.3.0': # Core Token
					core_fee += fee['amount']
				else:
					if not(fee_asset_id in other_fees):
						other_fees[fee_asset_id] = 0
					other_fees[fee_asset_id] += int(fee['amount'])
			
			nextstatus = getOperationNameForId(op_id).upper()
			details = iso.historyDescription(fake_obj)
			
			merge_in(root, op, nextstatus, details['long'], iso=iso)
		
		
		fee_text = ""
		if core_fee > 0:
			fee_text += str( iso.getAmount(core_fee, '1.3.0') ) + "\n"
		for fee_asset_id, amount in other_fees.items():
			fee_amt = iso.getAmount(amount, fee_asset_id)
			fee_text += str(fee_amt) + "\n"
		self.ui.feeTotal.setPlainText(fee_text)
		
		icon_s = qicon(":/icons/images/signed.png")
		icon_u = qicon(":/icons/images/unsigned.png")
		
		table = self.ui.signatureTable
		table.clear()
		table.setRowCount(0)
		self.ui.signedCheckbox.setChecked(False)
		self.ui.broadcastButton.setEnabled(False)
		
		j = -1
		if "missing_signatures" in trx:
			for sig in trx['missing_signatures']:
				j += 1
				table.insertRow(j)
				table.setItem(j, 0, QTableWidgetItem( "Missing: " + sig ))
				table.item(j, 0).setIcon(icon_u)
		
		if "signatures" in trx:
			for sig in trx['signatures']:
				j += 1
				table.insertRow(j)
				table.setItem(j, 0, QTableWidgetItem( sig ))
				table.item(j, 0).setIcon(icon_s)
		
		if "id" in trx: # HACK -- this could be set by history window
			self.setWindowTitle("Transaction " + trx["id"])
		
		if trx._is_signed():
			self.ui.signedCheckbox.setChecked(True)
			self.ui.broadcastButton.setEnabled(True)
	
	@classmethod
	def QRegisterAccount(self, registrar_name, referrer_name, data, fee_asset=None, isolator=None):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		registrarAccount = iso.getAccount(registrar_name)
		referrerAccount = iso.getAccount(referrer_name)
		
		if not(registrarAccount.is_ltm):
			showerror("%s is not a lifetime member" % registrar_name)
			return None
		
		params = {
			"registrar": registrarAccount['id'],
			"referrer": referrerAccount['id'],
			"referrer_percent": 100,
			"name": data['name'],
			"owner":  {
				'account_auths': [ ],
				'address_auths': [ ],
				'weight_threshold': 1,
				'key_auths': [
					[data['owner_key'],1]
				]
			},
			"active":  {
				'account_auths': [ ],
				'address_auths': [ ],
				'weight_threshold': 1,
				'key_auths': [
					[data['active_key'],1]
				]
			},
			"options": { 
				"memo_key": data['memo_key'],
				"votes": [ ],
				"voting_account": registrarAccount['id'],
				"num_witness": 0,
				"num_committee": 0,
			},
			"extensions": [ ]
		}
		
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		#from pprint import pprint
		#print("USE:")
		#pprint(params)
		
		tx.appendOps(Account_create(**params))
		
		if iso.bts.wallet.locked():
			tx.addSigningInformation(registrarAccount, "active", lazy=True)
		else:
			tx.appendSigner(registrarAccount, "active", lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		return win.exec_()
	
	
	@classmethod
	def QUpgradeAccount(self, account_name, fee_asset=None, isolator=None):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(account_name)
		params = {
			"account_to_upgrade": src_account['id'],
			"upgrade_to_lifetime_member": True,
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		from pprint import pprint
		print("USE:")
		pprint(params)
		
		tx.appendOps(Account_upgrade(**params))
		
		if iso.bts.wallet.locked():
			tx.addSigningInformation(src_account, "active", lazy=True)
		else:
			tx.appendSigner(src_account, "active", lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		return win.exec_()
	
	
	@classmethod
	def QUpdateAccount(self,
			account_name,
			owner_key,
			active_key,
			memo_key,
			voting_account,
			num_witness,
			num_committee,
			votes,
			fee_asset=None,
			isolator=None):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(account_name)
		dst_account = iso.getAccount(voting_account)
		params = {
			"account": src_account['id'],
		}
		from bitshares.blind import key_permission
		role = "active"
		if owner_key:
			owner_auth = key_permission(owner_key)
			params["owner"] = owner_auth
			role = "owner"
		if active_key:
			active_auth = key_permission(active_key)
			params["active"] = active_auth
			role = "owner"
		if not(votes is None):
			params["new_options"] = {
				"voting_account": dst_account["id"],
				"memo_key": memo_key if memo_key else src_account["options"]["memo_key"],
				"votes": votes,
				"num_witness": num_witness,
				"num_committee": num_committee,
			}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		from pprint import pprint
		print("USE:")
		pprint(params)
		
		tx.appendOps(Account_update(**params))
		
		if iso.bts.wallet.locked():
			tx.addSigningInformation(src_account, role, lazy=True)
		else:
			tx.appendSigner(src_account, role, lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		return win.exec_()

	@classmethod
	def QCreateWorker(self,
			worker_account,
			name, url,
			begin_date, end_date,
			daily_pay, worker_type,
			vesting_days=365,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(worker_account)
		if isinstance(daily_pay, float):
			daily_pay = int(daily_pay * 100000)
		if worker_type == "vesting" or worker_type == 1:
			work_init = (1, { "pay_vesting_period_days": vesting_days })
		elif worker_type == "burn" or worker_type == 2:
			work_init = (2, None)
		elif worker_type == "refund" or worker_type == 0:
			work_init = (0, None)
		else:
			raise ValueError("Unknown worker_type")
		params = {
			"owner": src_account['id'],
			"name": name,
			"url": url,
			"work_begin_date": begin_date.strftime("%Y-%m-%dT%H:%M:%S"),
			"work_end_date": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
			"daily_pay": daily_pay,
			"initializer": work_init
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		from pprint import pprint
		print("USE:")
		pprint(params)
		
		tx.appendOps(Worker_create(**params))
		
		
		if iso.bts.wallet.locked():
			tx.addSigningInformation(src_account, "active", lazy=True)
		else:
			tx.appendSigner(src_account, "active", lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		return win.exec_()

	@classmethod
	def QCreateAsset(self,
			issuer,
			symbol,
			precision,
			max_supply,
			permissions={ },
			flags={ },
			description="",
			market_fee_percent=0,
			core_exchange_rate=None,
			is_prediction_market=False,
			bitasset_options=None,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(issuer)
		permissions_int = toint(permissions)
		flags_int = toint(flags)
		#max_supply = total * pow(10, precision)
		#print("TOTAL:", total, "=> MAX SUPPLY:", max_supply)
		options = {
			"max_supply": max_supply, #satoshi
			"market_fee_percent": market_fee_percent, #0-100
			"max_market_fee": max_supply, # satoshi
			"issuer_permissions": permissions_int,
			"flags": flags_int,
			"core_exchange_rate" : {
				"base": {
					"amount": 1 * 100000,
					"asset_id": "1.3.0"},
				"quote": {
					"amount": 1 * pow(10, precision),
					"asset_id": "1.3.1"}},
			"whitelist_authorities" : [],
			"blacklist_authorities" : [],
			"whitelist_markets" : [],
			"blacklist_markets" : [],
			"description": description,
			"extensions": [],
		}
		if core_exchange_rate:
			core_exchange_rate["quote"]["asset_id"] = "1.3.1"
			options["core_exchange_rate"] = core_exchange_rate
		#bitasset_options = {
		#	"feed_lifetime_sec": 86400,
		#	"minimum_feeds": 1,
		#	"force_settlement_delay_sec": 86400,
		#	"force_settlement_offset_percent": 0,
		#	"maximum_force_settlement_volume": 2000,
		#	"short_backing_asset": "1.3.0"
		#	"extensions": []
		#}
		bitasset_options = {
			"feed_lifetime_sec": bitasset_options["feed_lifetime_sec"],
			"minimum_feeds": bitasset_options["minimum_feeds"],
			"force_settlement_delay_sec": bitasset_options["force_settlement_delay_sec"],
			"force_settlement_offset_percent": bitasset_options["force_settlement_offset_percent"],
			"maximum_force_settlement_volume": bitasset_options["maximum_force_settlement_volume"],
			"short_backing_asset": bitasset_options["short_backing_asset"],
			"extensions": []
		} if bitasset_options else None
		params = {
			"issuer": src_account['id'],
			"symbol": symbol,
			"precision": precision,
			"common_options": options,
			"bitasset_opts": bitasset_options,
			"is_prediction_market": is_prediction_market,
		}
		if not bitasset_options:
			params["is_prediction_market"] = False
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		from pprint import pprint
		print("USE:")
		pprint(params)
		
		tx.appendOps(Asset_create(**params))
		
		
		if iso.bts.wallet.locked():
			tx.addSigningInformation(src_account, "active", lazy=True)
		else:
			tx.appendSigner(src_account, "active", lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		return win.exec_()
	
	@classmethod
	def VUpdateFeedProducers(self,
			symbol,
			issuer,
			feed_producer_ids,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		src_account = iso.getAccount(issuer)
		asset = iso.getAsset(symbol)
		bitasset_options = asset['bitasset_data']
		params = {
			"issuer": src_account['id'],
			"asset_to_update": asset['id'],
			"new_feed_producers": feed_producer_ids,
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		return (Asset_update_feed_producers(**params), [(src_account, "active")])
	

	@classmethod
	def VPublishFeed(self,
			symbol,
			publisher,
			settlement_price,
			maintenance_collateral_ratio,
			maximum_short_squeeze_ratio,
			core_exchange_rate,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		src_account = iso.getAccount(publisher)
		asset = iso.getAsset(symbol)
		bitasset_options = asset['bitasset_data']
		params = {
			"publisher": src_account['id'],
			"asset_id": asset['id'],
			"feed": {
				"settlement_price": settlement_price,
				"maintenance_collateral_ratio": maintenance_collateral_ratio,
				"maximum_short_squeeze_ratio": maximum_short_squeeze_ratio,
				"core_exchange_rate": core_exchange_rate
			}
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		return (Asset_publish_feed(**params), [(src_account, "active")])

	@classmethod
	def QPublishFeed(self, *args, **kwargs):
		v = self.VPublishFeed(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)

	@classmethod
	def VUpdateBitAsset(self,
			symbol,
			issuer,
			feed_lifetime_sec,
			minimum_feeds,
			force_settlement_delay_sec,
			force_settlement_offset_percent,
			maximum_force_settlement_volume,
			short_backing_asset,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		src_account = iso.getAccount(issuer)
		asset = iso.getAsset(symbol)
		bitasset_options = asset['bitasset_data']
		bitasset_options.update({
			"feed_lifetime_sec": feed_lifetime_sec,
			"minimum_feeds": minimum_feeds,
			"force_settlement_delay_sec": force_settlement_delay_sec,
			"force_settlement_offset_percent": force_settlement_offset_percent,
			"maximum_force_settlement_volume": maximum_force_settlement_volume,
			"short_backing_asset": short_backing_asset,
		})
		params = {
			"issuer": src_account['id'],
			"asset_to_update": asset['id'],
			"new_options": bitasset_options,
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		return (Asset_update_bitasset(**params), [(src_account, "active")])
	
	@classmethod
	def VUpdateAsset(self,
			symbol,
			issuer,
			flags={ },
			description="",
			is_prediction_market=False,
			market_fee_percent=0,
			core_exchange_rate=None,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(issuer)
		new_account = None
		flags_int = toint(flags)
		asset = iso.getAsset(symbol)
		options = asset['options']
		options['description'] = description
		options['flags'] = flags_int
		options['market_fee_percent'] = market_fee_percent
		if core_exchange_rate:
			core_exchange_rate["quote"]["asset_id"] = asset["id"]
			options["core_exchange_rate"] = core_exchange_rate
		#options = {
		#	"market_fee_percent": 0, #1 - 1 percent?
		#	"flags": flags_int,
		#	"whitelist_authorities" : [],
		#	"blacklist_authorities" : [],
		#	"whitelist_markets" : [],
		#	"blacklist_markets" : [],
		#	"description": description,
		#}
		params = {
			"issuer": src_account['id'],
			"asset_to_update": asset['id'],
			"new_options": options,
		}
		if "is_prediction_market" in asset:
			params["is_prediction_market"] = is_prediction_market
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		return (Asset_update(**params), [(src_account, "active")])
	
	@classmethod
	def QUpdateAsset(self, *args, **kwargs):
		v = self.VUpdateAsset(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)
	
	@classmethod
	def VUpdateAssetIssuer(self,
			symbol,
			issuer,
			new_issuer,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(issuer)
		new_account = iso.getAccount(new_issuer)
		#if new_account["id"] == src_account["id"]:
		#	raise Exception
		asset = iso.getAsset(symbol)
		params = {
			"issuer": src_account['id'],
			"asset_to_update": asset['id'],
			"new_issuer": new_account['id']
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		return (Asset_update_issuer(**params), [(src_account, "owner")])
	
	@classmethod
	def QUpdateAssetIssuer(self, *args, **kwargs):
		v = self.VUpdateAssetIssuer(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)
	
	@classmethod
	def VGlobalSettle(self,
			symbol,
			issuer,
			settle_price,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		src_account = iso.getAccount(issuer)
		asset = iso.getAsset(symbol)
		params = {
			"issuer": src_account['id'],
			"asset_to_settle": asset['id'],
			"settle_price": settle_price
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		return (Asset_global_settle(**params), [(src_account, "active")])
	
	@classmethod
	def QGlobalSettle(self, *args, **kwargs):
		v = self.VGlobalSettle(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)


	@classmethod
	def VSettleAsset(self,
			from_account,
			symbol,
			amount_num,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		src_account = iso.getAccount(from_account)
		asset = iso.getAsset(symbol)
		params = {
			"account": src_account['id'],
			"amount": iso.getAmount(amount_num, asset["id"]).json(),
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		return (Asset_settle(**params), [(src_account, "active")])
	
	@classmethod
	def QSettleAsset(self, *args, **kwargs):
		v = self.VSettleAsset(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)


	@classmethod
	def QTransferToBlind(self,
			asset_id,
			amount_num,
			source_account,
			target_pubkey,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(source_account)
		asset = iso.getAsset(asset_id)
		amount = iso.getAmount(amount_num, asset_id).json()
		
		from bitshares.blind import gen_blind_outputs
		confirm, balances = gen_blind_outputs([
			[ target_pubkey, amount["amount"] ]
		], asset["id"]
		#,debug_priv="5JG5w3hXMq1fb32hzzd3CSWj4EMXeX6tiN2yxJf6SYZ8eZJ4EBB"
		)
		
		params = {
			"amount": confirm["amount"],
			"from": src_account['id'],
			"blinding_factor": confirm["blinding_factor"],
			"outputs": confirm["outputs"],
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		from pprint import pprint
		print("USE:")
		pprint(params)
		
		tx.appendOps(Transfer_to_blind(**params))
		if iso.bts.wallet.locked():
			tx.addSigningInformation(src_account, "active", lazy=True)
		else:
			tx.appendSigner(src_account, "active", lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		r = win.exec_()
		if not r:
			return False
		for b in balances:
			b["description"] = "from @" + src_account["name"]
		win._receiveBlindTransfers(iso, balances, [ ], comment1="@"+src_account["name"])
		return True
	
	@classmethod
	def QTransferFromBlind(self,
			asset_id,
			amount_num,
			source_pubkey,
			target_account,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		dst_account = iso.getAccount(target_account)
		asset = iso.getAsset(asset_id)
		amount = iso.getAmount(amount_num, asset_id).json()

		from bitshares.blind import transfer_from_blind
		confirm = transfer_from_blind(blockchain_instance,
			source_pubkey,
			dst_account["id"],
			amount["amount"],
			asset["symbol"],
			broadcast = False
		#,debug_priv="5JG5w3hXMq1fb32hzzd3CSWj4EMXeX6tiN2yxJf6SYZ8eZJ4EBB"
		)
		tx = confirm["trx"]
#		if fee_asset:
#			params['fee'] = iso.getAmount(0, fee_asset).json()
#		else:
#			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
#		
#		from pprint import pprint
#		print("USE:")
#		pprint(params)
#		
#		tx.appendOps(Transfer_from_blind(**params))
#		if iso.bts.wallet.locked():
#			tx.addSigningInformation(dst_account, "active", lazy=True)
#		else:
#			tx.appendSigner(dst_account, "active", lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		r = win.exec_()
		if not r:
			return False
		win._receiveBlindTransfers(iso, confirm["balances"], confirm["inputs"], to_temp=True)
		return True
	
	@classmethod
	def QBlindTransfer(self,
			asset_id,
			amount_num,
			source_pubkey, #TODO: or_label?
			target_pubkey, #_or_label
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		asset = iso.getAsset(asset_id)
		amount = iso.getAmount(amount_num, asset_id).json()
		
		from bitshares.blind import blind_transfer
		confirm = blind_transfer(blockchain_instance,
			source_pubkey,
			target_pubkey,
			amount["amount"],
			asset["symbol"],
			broadcast = False,
			sign = False
		#,debug_priv="5JG5w3hXMq1fb32hzzd3CSWj4EMXeX6tiN2yxJf6SYZ8eZJ4EBB"
		)
		tx = confirm["trx"]
#		if fee_asset:
#			params['fee'] = iso.getAmount(0, fee_asset).json()
#		else:
#			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
#		
#		from pprint import pprint
#		print("USE:")
#		pprint(params)
#		
#		tx.appendOps(Blind_transfer(**params))
#		if iso.bts.wallet.locked():
#			tx.addSigningInformation(dst_account, "active", lazy=True)
#		else:
#			tx.appendSigner(dst_account, "active", lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		r = win.exec_()
		if not r:
			return False
		win._receiveBlindTransfers(iso, confirm["balances"], confirm["inputs"])
		return True
	
	def _receiveBlindTransfers(self, iso, balances, inputs, comment1="", to_temp=False):
		from bitshares.blind import receive_blind_transfer
		from bitshares.blind import refresh_blind_balances
		for i, b in enumerate(balances):
			is_temp = False
			if to_temp and i == len(balances) - 1:
				is_temp = True
			try:
				receive_blind_transfer(iso.bts.wallet, b["receipt"], comment1, b["description"], to_temp=is_temp)
			except:
				log.exception("Failed to store balance")
				iso.bts.wallet.storeBlindBalance(b)
		refresh_blind_balances(iso.bts.wallet, inputs, storeback=True)
	
	@classmethod
	def QIssueAsset(self,
			asset_id,
			amount_num,
			source_account,
			target_account,
			memo=None,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(source_account)
		params = {
			"asset_to_issue": iso.getAmount(amount_num, asset_id).json(),
			"issuer": iso.getAccount(source_account)['id'],
			"issue_to_account": iso.getAccount(target_account)['id'],
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		if memo:
			params['memo'] = iso.getMemo(source_account, target_account, memo)
		
		from pprint import pprint
		print("USE:")
		pprint(params)
		
		tx.appendOps(Asset_issue(**params))
		
		if iso.bts.wallet.locked():
			tx.addSigningInformation(src_account, "active", lazy=True)
		else:
			tx.appendSigner(src_account, "active", lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		return win.exec_()
	
	@classmethod
	def QReserveAsset(self,
			asset_id,
			amount_num,
			source_account,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(source_account)
		params = {
			"amount_to_reserve": iso.getAmount(amount_num, asset_id).json(),
			"payer": iso.getAccount(source_account)['id'],
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		from pprint import pprint
		print("USE:")
		pprint(params)
		
		tx.appendOps(Asset_reserve(**params))
		
		if iso.bts.wallet.locked():
			tx.addSigningInformation(src_account, "active", lazy=True)
		else:
			tx.appendSigner(src_account, "active", lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		return win.exec_()
	
	
	@classmethod
	def QFundFeePool(self,
			asset_id,
			core_amount_num,
			source_account,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(source_account)
		asset = iso.getAsset(asset_id)
		amount = iso.getAmount(core_amount_num, "1.3.0").json()
		params = {
			"from_account": iso.getAccount(source_account)['id'],
			"asset_id": asset["id"],
			"amount": int(amount["amount"]),
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		from pprint import pprint
		print("USE:")
		pprint(params)
		
		tx.appendOps(Asset_fund_fee_pool(**params))
		if iso.bts.wallet.locked():
			tx.addSigningInformation(src_account, "active", lazy=True)
		else:
			tx.appendSigner(src_account, "active", lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		return win.exec_()
	
	@classmethod
	def VClaimFeePool(self,
			asset_id,
			core_amount_num,
			source_account,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(source_account)
		asset = iso.getAsset(asset_id)
		amount = iso.getAmount(core_amount_num, "1.3.0").json()
		params = {
			"issuer": iso.getAccount(source_account)['id'],
			"asset_id": asset["id"],
			"amount_to_claim": {
				"asset_id": amount["asset_id"],
				"amount": int(amount["amount"]),
			}
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		return (Asset_claim_pool(**params), [(src_account, "active")])
	
	@classmethod
	def QClaimFeePool(self, *args, **kwargs):
		v = self.VClaimFeePool(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)
	
	
	@classmethod
	def VClaimMarketFees(self,
			asset_id,
			amount_num,
			source_account,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(source_account)
		amount = iso.getAmount(amount_num, asset_id).json()
		params = {
			"issuer": iso.getAccount(source_account)['id'],
			"amount_to_claim": {
				"asset_id": amount["asset_id"],
				"amount": int(amount["amount"]),
			}
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		return (Asset_claim_fees(**params), [(src_account, "active")])
	
	@classmethod
	def QClaimMarketFees(self, *args, **kwargs):
		v = self.VClaimMarketFees(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)
	
	
	@classmethod
	def VOverrideTransfer(self,
			asset_id,
			amount_num,
			issuer_account,
			source_account,
			target_account,
			memo=None,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		tx = TransactionBuilder(blockchain_instance=iso.bts)
		iss_account = iso.getAccount(issuer_account)
		params = {
			"amount": iso.getAmount(amount_num, asset_id).json(),
			"issuer": iso.getAccount(issuer_account)['id'],
			"from": iso.getAccount(source_account)['id'],
			"to": iso.getAccount(target_account)['id'],
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		if memo:
			with iso.unlockedWallet() as w:
				params['memo'] = iso.getMemo(issuer_account, target_account, memo)
		
		return (Override_transfer(**params), [(iss_account, "active")])
	
	@classmethod
	def QOverrideTransfer(self, *args, **kwargs):
		v = self.VOverrideTransfer(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)
	
	
	@classmethod
	def VSellAsset(self,
			source_account,
			sell_asset_id,
			sell_amount,
			buy_asset_id,
			buy_amount,
			expiration=3600 * 24,
			fill_or_kill=False,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(source_account)
		params = {
			"seller": iso.getAccount(source_account)['id'],
			"amount_to_sell": iso.getAmount(sell_amount, sell_asset_id).json(),
			"min_to_receive": iso.getAmount(buy_amount, buy_asset_id).json(),
			"expiration": expiration,
			"fill_or_kill": fill_or_kill,
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		
		import datetime
		now = datetime.datetime.utcnow()
		add = datetime.timedelta(seconds=expiration)
		params["expiration"] = (now+add).strftime("%Y-%m-%dT%H:%M:%S")
		
		from pprint import pprint
		print("USE:")
		pprint(params)
		
		return (Limit_order_create(**params), [(src_account, "active")])
	
	@classmethod
	def QSellAsset(self, *args, **kwargs):
		v = self.VSellAsset(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)
	
	@classmethod
	def VCancelOrder(self,
			source_account,
			order_id,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts
		tx = TransactionBuilder(blockchain_instance=blockchain_instance)
		src_account = iso.getAccount(source_account)
		params = {
			"fee_paying_account": iso.getAccount(source_account)['id'],
			"order": order_id,
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		
		from pprint import pprint
		print("USE:")
		pprint(params)
		
		return (Limit_order_cancel(**params), [(src_account, "active")])
	
	@classmethod
	def QCancelOrder(self, *args, **kwargs):
		v = self.VCancelOrder(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)
	
	@classmethod
	def VTransfer(self,
			asset_id,
			amount_num,
			source_account,
			target_account,
			memo=None,
			fee_asset=None,
			isolator=None
		):
		iso = isolator
		tx = TransactionBuilder(blockchain_instance=iso.bts)
		src_account = iso.getAccount(source_account)
		params = {
			"amount": iso.getAmount(amount_num, asset_id).json(),
			"from": iso.getAccount(source_account)['id'],
			"to": iso.getAccount(target_account)['id'],
		}
		if fee_asset:
			params['fee'] = iso.getAmount(0, fee_asset).json()
		else:
			params['fee'] = {"amount": 0, "asset_id": "1.3.0"}
		if memo:
			with iso.unlockedWallet() as w:
				params['memo'] = iso.getMemo(source_account, target_account, memo)
		
		return (Transfer(**params), [(src_account, "active")])
	
	@classmethod
	def QTransfer(self, *args, **kwargs):
		v = self.VTransfer(*args, **kwargs)
		return self._QExec(kwargs.get("isolator"), v)
	
	@classmethod
	def _QExec(self, iso, v):
		return self._QExecS(iso, [v])
	
	@classmethod
	def _QExecS(self, iso, vs):
		tx = TransactionBuilder(blockchain_instance=iso.bts)
		for (op, sigs) in vs:
			tx.appendOps(op)
			for (account,role) in sigs:
				if iso.bts.wallet.locked():
					tx.addSigningInformation(account, role, lazy=True)
				else:
					tx.appendSigner(account, role, lazy=True)
		
		win = QTransactionBuilder(trxbuffer=tx, iso=iso)
		return win.exec_()
	
	@classmethod
	def QViewTransaction(self,
			trx,
			highlight=-1,
			isolator=None
		):
		iso = isolator
		blockchain_instance = iso.bts


		trx["operations"] = [
			getOperationClassForId(op_id)(**op)
			for (op_id, op) in trx["operations"]
		]
		tx = TransactionBuilder(trx, blockchain_instance=blockchain_instance)
		
		#for (op_id, op) in trx["operations"]:
		#	op_klass = getOperationClassForId(op_id)
		#	log.debug("getOpertationClassForId %d yields %s" % (op_id, op_klass.__name__))
		#	tx.appendOps(op_klass(**op))
		
		#if "signatures" in trx:
		#	tx["signatures"] = trx["signatures"]
		#
		#if "missing_signatures" in trx:
		#    tx["missing_signatures"] = trx["missing_signatures"]
		
		win = QTransactionBuilder(trxbuffer=tx, iso=isolator)
		win.setPreviewMode(True)
		win.highlightOp(highlight)
		return win.exec_()
	