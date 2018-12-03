from PyQt5 import QtCore, QtGui

from .utils import *
import logging
log = logging.getLogger(__name__)

from pprint import pprint
import json

from .isolator import ResourceUnavailableOffline, WalletLocked
#from bitshares import BitShares
#from bitshares.account import Account
#from bitsharesbase.account import PasswordKey
from bitsharesbase.account import PrivateKey
from bitsharesbase.account import BrainKey

from .transactionbuilder import QTransactionBuilder

class WindowWithBlind(QtCore.QObject):

	def init_blind(self):
		self._activeBlindAccount = None
		
		self.ui.viewBlindCreate.clicked.connect(self.ba_page_create)
		self.ui.viewBlindContact.clicked.connect(self.ba_page_contact)
		self.ui.blindAccountCancel.clicked.connect(self.ba_page_balances)
		self.ui.blindContactCancel.clicked.connect(self.ba_page_balances)
		
		self.ui.viewBlindFrom.clicked.connect(self.bt_page_from)
		self.ui.viewBlindTo.clicked.connect(self.bt_page_to)
		self.ui.viewBlindTransfer.clicked.connect(self.bt_page_transfer)
		self.ui.viewBlindReceive.clicked.connect(self.bt_page_receive)
		self.ui.viewBlindNone.clicked.connect(self.bt_page_none)
		
		self.uiAccountAssetLink(self.ui.blindFromAccount, self.ui.blindFromAsset)
		self.uiAccountAssetLink(self.ui.blindFromAccount, self.ui.blindFromFeeAsset)
		self.uiAccountAssetLink(self.ui.blindToAccount, self.ui.blindToFeeAsset)
		
		self.uiAssetLink(self.ui.blindFromAmount, self.ui.blindFromAsset)
		self.uiAssetLink(self.ui.blindToAmount, self.ui.blindToAsset)
		self.uiAssetLink(self.ui.blindAmount, self.ui.blindAsset)
		
		#self.uiBlindAccountAssetLink(self.ui.blindToSource, self.ui.blindFromAsset)
		self.uiBlindAccountAssetLink(self.ui.blindSource, self.ui.blindToAsset)
		
		self.ba_page_balances()
		self.bt_page_none()
		
		self.ui.blindAccountGenerate.clicked.connect(self.generate_blind_brainkey)
		self.ui.blindAccountCreate.clicked.connect(self.create_blind_account)
		self.ui.blindContactCreate.clicked.connect(self.create_blind_contact)
		
		self.ui.blindFromTransfer.clicked.connect(self.transfer_to_blind)
		self.ui.blindToTransfer.clicked.connect(self.transfer_from_blind)
		self.ui.blindTransfer.clicked.connect(self.transfer_blind_blind)
		self.ui.blindReceive.clicked.connect(self.receive_blind_transfer)
		
		self.ui.blindAccounts.setColumnCount(2)
		self.ui.blindHistory.setColumnCount(3)
		stretch_table(self.ui.blindAccounts, hidehoriz=True)
		stretch_table(self.ui.blindBalances, hidehoriz=True)
		stretch_table(self.ui.blindHistory, hidehoriz=True)
		
		qmenu(self.ui.blindAccounts, self.show_blindaccounts_submenu)
		qmenu(self.ui.blindBalances, self.show_blindbalances_submenu)
		qmenu(self.ui.blindHistory, self.show_blindhistory_submenu)
		
		self.ui.blindAccounts.itemChanged.connect(self.edit_blind_account)
		self.ui.blindAccounts.itemSelectionChanged.connect(self.activate_blind_account)
		self.ui.blindHistory.itemChanged.connect(self.edit_blind_history)
	
	def uiBlindAccountAssetLink(self, accCombo, symCombo):
		if not hasattr(accCombo, '_linkedAssets'):
			accCombo._linkedAssets = [ ]
		accCombo._linkedAssets.append( symCombo )
		#accCombo.currentIndexChanged.connect(self.uiBlindAccountAssetLink_perform)
		on_combo(accCombo, self.uiBlindAccountAssetLink_perform)
	
	def uiBlindAccountAssetLink_perform(self):
		accCombo = self.sender()
		symCombos = accCombo._linkedAssets
		blind_label_or_key = accCombo.currentText().strip()
		if not len(blind_label_or_key):
			accCombo.setFocus()
			return
		
		account = self._get_blind_account(blind_label_or_key)
		if not account:
			return
		
		for symCombo in symCombos:
			symCombo.clear()
		
		balances = self._get_blind_balances(account["pub"])
		for asset_id, amount in balances.items():
			amount = self.iso.getAmount(int(amount), asset_id)
			for symCombo in symCombos:
				symCombo.addItem(amount.symbol)
	
	def show_blindaccounts_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Copy Public Key", self._blacc_copy_pubkey)
		menu.addSeparator()
		qaction(self, menu, "Remove", self._blacc_remove)
		menu.addSeparator()
		qaction(self, menu, "Show Private Key", self._blacc_show_privkey)
		qmenu_exec(self.ui.blindAccounts, menu, position)
	
	def show_blindbalances_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Blind Transfer...", self._blbal_transfer)
		qaction(self, menu, "Unblind...", self._blbal_unblind)
		menu.addSeparator()
		qaction(self, menu, "Copy Balance", self._blbal_copy_balance)
		qmenu_exec(self.ui.blindBalances, menu, position)
	
	def show_blindhistory_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Show Receipt", self._blhist_show_receipt)
		qaction(self, menu, "Copy Receipt", self._blhist_copy_receipt)
		menu.addSeparator()
		qmenu_exec(self.ui.blindHistory, menu, position)
	
	def _blacc_copy_pubkey(self):
		j = table_selrow(self.ui.blindAccounts)
		if j <= -1: return
		pubkey = self.ui.blindAccounts.item(j, 1).text()
		qclip(pubkey)
	
	def _blacc_remove(self):
		table = self.ui.blindAccounts
		j = table_selrow(table)
		if j <= -1: return
		label = table.item(j, 0).text()
		pubkey = table.item(j, 1).text()
		nkeys = self.iso.store.countPrivateKeys([pubkey])
		if nkeys > 0:
			if not(askyesno("Really delete blind account " + label + " ?")):
				return
			self.iso.bts.wallet.removePrivateKeyFromPublicKey(pubkey)
			self.iso.store.blindAccountStorage.update(pubkey, 'keys', 0)
			table.item(j, 0).setIcon(qicon(":/op/images/op/blind_transfer.png"))
		else:
			self.iso.store.blindAccountStorage.delete(pubkey)
			table.removeRow(j)
	
	def _blacc_show_privkey(self):
		j = table_selrow(self.ui.blindAccounts)
		if j <= -1: return
		label =  self.ui.blindAccounts.item(j, 0).text()
		pubkey = self.ui.blindAccounts.item(j, 1).text()
		
		try:
			with self.iso.unlockedWallet(
				reason='View Private Keys for ' + label
			) as w:
				priv = self.iso.getPrivateKeyForPublicKeys([pubkey])[0]
		except WalletLocked:
			return
		except Exception as exc:
			showexc(exc)
			return
		
		showdialog("Private key for blind account",
			additional=label,
			details=priv, min_width=240)

	
	def _blbal_transfer(self):
		j = table_selrow(self.ui.blindBalances)
		if j <= -1:
			return
		amount = self.ui.blindBalances.item(j, 0).text()
		symbol = self.ui.blindBalances.item(j, 1).text()
		
		set_combo(self.ui.blindSource, self._activeBlindAccount)
		set_combo(self.ui.blindAsset, symbol)
		self.ui.blindAmount.setValue(float(amount))
		self.bt_page_transfer()
	
	def _blbal_unblind(self):
		j = table_selrow(self.ui.blindBalances)
		if j <= -1:
			return
		amount = self.ui.blindBalances.item(j, 0).text()
		symbol = self.ui.blindBalances.item(j, 1).text()
		
		set_combo(self.ui.blindToSource, self._activeBlindAccount)
		set_combo(self.ui.blindToAsset, symbol)
		self.ui.blindToAmount.setValue(float(amount))
		self.bt_page_from()
	
	def _blbal_copy_balance(self):
		j = table_selrow(self.ui.blindBalances)
		if j <= -1:
			return
		amount = self.ui.blindBalances.item(j, 0).text()
		symbol = self.ui.blindBalances.item(j, 1).text()
		qclip(amount)
	
	def _blhist_show_receipt(self):
		j = table_selrow(self.ui.blindHistory)
		if j <= -1:
			return
		balance = self.ui.blindHistory.item(j, 0).data(99)
		
		txt2 = ""
		text = ""
		n = 0
		
		text += "Commitment " + balance["commitment"]
		text += "\n " + balance["description"]
		text += "\n Receipt: " + balance["receipt"]
		text += "\n\n"
		n += 1
		txt2 += "\n" + balance["receipt"]
		
		if n == 0:
			showerror("No receipts found")
			return
		
		showmsg("Found %d blind receipt(s)" % n, additional=txt2, details=text)
	
	def _blhist_copy_receipt(self):
		j = table_selrow(self.ui.blindHistory)
		if j <= -1: return
		balance = self.ui.blindHistory.item(j, 0).data(99)
		qclip(balance["receipt"])
	
	def activate_blind_account(self):
		table = self.ui.blindAccounts
		j = table_selrow(table)
		if j <= -1: return
		
		label = table.item(j, 0).text()
		public_key = table.item(j, 1).text()
		nkeys = table_coldata(table, j, 0)
		
		value = label if label and len(label) else public_key
		self._activeBlindAccount = value
		
		set_combo(self.ui.blindFromDestination, value)
		set_combo(self.ui.blindToSource, value)
		if nkeys:
			set_combo(self.ui.blindSource, value)
		else:
			set_combo(self.ui.blindDestination, value)
		
		self.refresh_blind_account()
	
	def refresh_blind_account(self):
		table = self.ui.blindAccounts
		j = table_selrow(table)
		if j <= -1: return
		
		public_key = table.item(j, 1).text()
		
		self.reload_blind_history(public_key)
		self.reload_blind_balances(public_key)
	
	def edit_blind_account(self, item):
		store = self.iso.store.blindAccountStorage
		table = self.ui.blindAccounts
		
		j = item.row()
		
		label = table.item(j, 0).text()
		public_key = table.item(j, 1).text()
		
		old_label = store.getByPublicKey(public_key)["label"]
		if old_label == label:
			return
		
		store.update(public_key, "label", label)
	
	def edit_blind_history(self, item):
		store = self.iso.store.blindStorage
		table = self.ui.blindHistory
		
		j = item.row()
		
		entry = table.item(j, 0).data(99)
		commitment = entry["commitment"]
		description = table.item(j, 2).text() if table.item(j, 2) else ""
		
		store.update(commitment, "description", description)
	
	def generate_blind_brainkey(self):
		bk = BrainKey() # this will generate a new one
		self.ui.blindBrainkeyPlain.setPlainText(bk.get_brainkey())
	
	def create_blind_account(self):
		label = self.ui.blindLabel.text()
		generated = self.ui.blindBrainkeyPlain.toPlainText().strip()
		if len(generated) == 0:
			self.ui.blindBrainkeyPlain.setFocus()
			return
		if len(label) == 0:
			self.ui.blindLabel.setFocus()
			return
		bk = BrainKey(generated)
		
		bk.sequence = 0
		owner_key = bk.get_blind_private()
		
		private_key = owner_key
		
		private_wif = str(private_key)
		public_key = str(private_key.pubkey)
		
		try:
			with self.iso.unlockedWallet(
				reason='Add new blind account'
			) as w:
				self.iso.store.blindAccountStorage.add(
					public_key,
					label
				)
				self.iso.store.keyStorage.add(
					private_wif,
					public_key
			)
		except WalletLocked:
			return
		except Exception as exc:
			showexc(exc)
			return
		
		table = self.ui.blindAccounts
		n = table.rowCount()
		
		self._insert_blind_account_row(n, label, public_key, 1)
		
		self.ui.blindLabel.setText("")
		self.ui.blindBrainkeyPlain.setPlainText("")
		self.ba_page_balances()
	
	def create_blind_contact(self):
		label = self.ui.blindContactLabel.text().strip()
		public_key = self.ui.blindContactPubkey.text().strip()
		if len(public_key) == 0:
			self.ui.blindContactPubkey.setFocus()
			return
		if len(label) == 0:
			self.ui.blindContactLabel.setFocus()
			return
		
		from bitsharesbase.account import PublicKey
		try:
			test = PublicKey(public_key)
		except Exception as e:
			showerror("Not a valid Public Key: " + str(e))
			return
		try:
			self.iso.store.blindAccountStorage.add(
				public_key,
				label,
				keys = 0
			)
		except Exception as e:
			showexc(e)
			return
		
		table = self.ui.blindAccounts
		n = table.rowCount()
		
		self._insert_blind_account_row(n, label, public_key, 0)
		
		self.ui.blindContactLabel.setText("")
		self.ui.blindContactPubkey.setText("")
		self.ba_page_balances()
	




	def loadBlindAccounts(self):
		table = self.ui.blindAccounts
		accounts = self.iso.store.blindAccountStorage.getAccounts()
		contacts = self.iso.store.blindAccountStorage.getContacts()
		
		j = table.rowCount() - 1
		for a in contacts:
			j += 1
			
			self._insert_blind_account_row(j, a["label"], a["pub"], a["keys"])
	
	def _insert_blind_account_row(self, j, label, public_key, keys):
		table = self.ui.blindAccounts
		table.blockSignals(True)
		table.insertRow(j)
		
		if not keys:
			icon = qicon(":/op/images/op/blind_transfer.png")
		else:
			icon = qicon(":/icons/images/account_suit.png")
		
		set_col(table, j, 0, label, editable=True, icon=icon, data=keys)
		set_col(table, j, 1, public_key, editable=False, data=keys)
		
		table.blockSignals(False)
	
	def reload_blind_history(self, pubkey):
		store = self.iso.store.blindStorage
		entries = store.getEntriesBy([("pub_to", pubkey),("pub_from", pubkey)], False)
		balances = { }
		
		table = self.ui.blindHistory
		table.setRowCount(0)
		
		table.blockSignals(True)
		j = -1
		for entry in entries:
			j += 1
			table.insertRow(j)
			
			#asset = self.iso.getAsset(entry["asset_id"], force_remote=False)
			amount = self.iso.getAmount(int(entry["amount"]), entry["asset_id"])
			incom = bool(pubkey == entry["pub_to"])
			if not(entry["pub_to"]):
				incom = False

			#print("***")
			#print(entry)
			#print("***")

			color = COLOR_GREEN if incom else COLOR_RED
			if not(entry["description"]):
				if incom and not(entry["pub_from"]):
					d = "from regular account"
				elif incom and entry["pub_from"] == entry["pub_to"]:
					d = "change"
				elif incom:
					d = "from " + entry["pub_from"]
				elif entry["pub_to"]:
					d = "to " + entry["pub_to"]
				else:
					d = "to regular account"
				entry["description"] = d
			
			set_col(table, j, 0, str(entry["date"]), data=entry, editable=False)
			item = set_col(table, j, 1, str(amount), color=color, align="right", editable=False)
			if entry["used"]:
				item.setBackground(QtGui.QColor('#eeeeee'))
			set_col(table, j, 2, entry["description"], editable=True)
		table.blockSignals(False)
	
	def _get_blind_account(self, label_or_key):
		account = None
		store = self.iso.store.blindAccountStorage
		try:
			account = store.getByPublicKey(label_or_key)
		except:
			try:
				account = store.getByLabel(label_or_key)
			except:
				pass
		return account
	
	def _get_blind_balances(self, pubkey):
		store = self.iso.store.blindStorage
		entries = store.getEntriesBy([("pub_to", pubkey)])
		balances = { }
		for entry in entries:
			if entry["used"]:
				continue
			asset_id = entry["asset_id"]
			if not(asset_id in balances):
				balances[asset_id] = 0
			balances[asset_id] += entry["amount"]
		return balances
	
	def reload_blind_balances(self, pubkey):
		balances = self._get_blind_balances(pubkey)
		table = self.ui.blindBalances
		table.setRowCount(0)
		
		j = -1
		for asset_id, amount in balances.items():
			j += 1
			table.insertRow(j)
			
			amount = self.iso.getAmount(amount, asset_id)
			table.setItem(j, 0, QtGui.QTableWidgetItem(amount.formated))
			table.setItem(j, 1, QtGui.QTableWidgetItem(amount.symbol))
			table.item(j, 0).setIcon( qicon(":/icons/images/token.png") )
			
			self.blind_asset_add(amount.symbol)
	
	def blind_asset_add(self, symbol):
		boxes = [
			self.ui.blindToAsset,
			self.ui.blindAsset,
			self.ui.blindFeeAsset,
		]
		for box in boxes:
			sync_combo(box, [symbol])
	
	def transfer_to_blind(self):
		account_from = self.ui.blindFromAccount.currentText()
		blind_to = self.ui.blindFromDestination.currentText()
		asset_name = self.ui.blindFromAsset.currentText()
		asset_amount = self.ui.blindFromAmount.text()
		
		if not(blind_to.startswith("BTS")):
			blind_account = self.iso.store.blindAccountStorage.getByLabel(blind_to)
			if not blind_account:
				showerror("Unknown blind account " + blind_to)
				return
			public_key = blind_account['pub']
		else:
			public_key = blind_to
		
		fee_asset = anyvalvis(self.ui.blindFromFeeAsset, None)#.currentText()
		
		try:
			r = QTransactionBuilder.QTransferToBlind(
				asset_name,
				asset_amount,
				account_from,
				public_key,
				fee_asset=fee_asset,
				isolator=self.iso)
		except Exception as error:
			showexc(error)
			return
		
		if not r:
			return
		
		self.refresh_blind_account()
		set_combo(self.ui.blindFromDestination, "")
		self.ui.blindFromAmount.setValue(0)
	
	def transfer_from_blind(self):
		account_to = self.ui.blindToAccount.currentText()
		blind_from = self.ui.blindToSource.currentText()
		asset_name = self.ui.blindToAsset.currentText()
		asset_amount = self.ui.blindToAmount.text()
		
		if not(blind_from.startswith("BTS")):
			blind_account = self.iso.store.blindAccountStorage.getByLabel(blind_from)
			if not blind_account:
				showerror("Unknown blind account " + blind_from)
				return
			public_key = blind_account['pub']
		else:
			public_key = blind_from
		
		fee_asset = anyvalvis(self.ui.blindToFeeAsset, None)#.currentText()
		
		from bitshares.exceptions import InsufficientBlindBalance
		try:
			r = QTransactionBuilder.QTransferFromBlind(
				asset_name,
				asset_amount,
				public_key,
				account_to,
				fee_asset=fee_asset,
				isolator=self.iso)
		except InsufficientBlindBalance as error:
			self.refresh_blind_account() # !
			if error.input_adjust < 0:
				adjust_float = error.input_adjust / 10 ** error.asset_obj["precision"]
				adjusted_value = float(asset_amount) + adjust_float
				self.ui.blindToAmount.setValue(adjusted_value)
			showexc(error)
			return
		except Exception as error:
			showexc(error)
			return
		
		if not r:
			return
		
		self.refresh_blind_account()
		set_combo(self.ui.blindToAccount, "")
		self.ui.blindToAmount.setValue(0)
	
	def transfer_blind_blind(self):
		blind_from = self.ui.blindSource.currentText()
		blind_to = self.ui.blindDestination.currentText()
		asset_name = self.ui.blindAsset.currentText()
		asset_amount = self.ui.blindAmount.text()
		
		if not(blind_to.startswith("BTS")):
			blind_account_to = self.iso.store.blindAccountStorage.getByLabel(blind_to)
			if not blind_account_to:
				showerror("Unknown blind account " + blind_to)
				return
			public_key_to = blind_account_to['pub']
		else:
			public_key_to = blind_to
		
		if not(blind_from.startswith("BTS")):
			blind_account_from = self.iso.store.blindAccountStorage.getByLabel(blind_from)
			if not blind_account_from:
				showerror("Unknown blind account " + blind_from)
				return
			public_key_from = blind_account_from['pub']
		else:
			public_key_from = blind_from
		
		fee_asset = anyvalvis(self.ui.blindFeeAsset, None)#.currentText()
		
		from bitshares.exceptions import InsufficientBlindBalance
		try:
			r = QTransactionBuilder.QBlindTransfer(
				asset_name,
				asset_amount,
				public_key_from,
				public_key_to,
				fee_asset=fee_asset,
				isolator=self.iso)
		except InsufficientBlindBalance as error:
			self.refresh_blind_account() # !
			if error.input_adjust < 0:
				adjust_float = error.input_adjust / 10 ** error.asset_obj["precision"]
				adjusted_value = float(asset_amount) + adjust_float
				self.ui.blindAmount.setValue(adjusted_value)
			showexc(error)
			return
		except Exception as error:
			showexc(error)
			return
		
		if not r:
			return
		
		self.refresh_blind_account()
		set_combo(self.ui.blindDestination, "")
		self.ui.blindAmount.setValue(0)
	
	def receive_blind_transfer(self):
		receipt = self.ui.blindReceipt.text().strip()
		if not receipt:
			self.ui.blindReceipt.setFocus()
			return
		wallet = self.iso.bts.wallet
		comment1 = comment2 = ""
		
		from bitshares.blind import receive_blind_transfer
		try:
			ok, _, _ = receive_blind_transfer(wallet, receipt, comment1, comment2)
		except Exception as error:
			showexc(error)
			return
		if not ok:
			return
		
		self.ui.blindReceipt.setText("")
		self.refresh_blind_account()
	
	def ba_page_balances(self):
		self.ui.blindStack2.setCurrentIndex(0)
		self.ui.viewBlindCreate.setVisible(True)
		self.ui.viewBlindContact.setVisible(True)
	
	def ba_page_create(self):
		self.ui.blindStack2.setCurrentIndex(1)
		self.ui.viewBlindCreate.setVisible(False)
		self.ui.viewBlindContact.setVisible(False)
	
	def ba_page_contact(self):
		self.ui.blindStack2.setCurrentIndex(2)
		self.ui.viewBlindCreate.setVisible(False)
		self.ui.viewBlindContact.setVisible(False)
	
	def bt_page_none(self):
		self.ui.blindStack.setVisible(False)
		self.ui.viewBlindNone.setEnabled(False)
		self._bt_page_highlight_buttons(-1)
	
	def bt_page_to(self):
		self.ui.blindStack.setCurrentIndex(0)
		self.ui.blindStack.setVisible(True)
		self.ui.viewBlindNone.setEnabled(True)
		self._bt_page_highlight_buttons(0)
	def bt_page_from(self):
		self.ui.blindStack.setCurrentIndex(1)
		self.ui.blindStack.setVisible(True)
		self.ui.viewBlindNone.setEnabled(True)
		self._bt_page_highlight_buttons(1)
	def bt_page_transfer(self):
		self.ui.blindStack.setCurrentIndex(2)
		self.ui.blindStack.setVisible(True)
		self.ui.viewBlindNone.setEnabled(True)
		self._bt_page_highlight_buttons(2)
	def bt_page_receive(self):
		self.ui.blindStack.setCurrentIndex(3)
		self.ui.blindStack.setVisible(True)
		self.ui.viewBlindNone.setEnabled(True)
		self._bt_page_highlight_buttons(3)
	
	def _bt_page_highlight_buttons(self, index):
		buttons = [
			self.ui.viewBlindTo,
			self.ui.viewBlindFrom,
			self.ui.viewBlindTransfer,
			self.ui.viewBlindReceive,
		]
		j = -1
		for btn in buttons:
			j += 1
			if j == index:
				btn.setChecked(True)
			else:
				btn.setChecked(False)
	