from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.keyswindow import Ui_KeysWindow

from .isolator import WalletLocked

from .utils import *
import json

import logging
log = logging.getLogger(__name__)

class KeysWindow(QtWidgets.QDialog):

	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('isolator', None)
		self._ret = 0
		super(KeysWindow, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_KeysWindow()
		ui.setupUi(self)
		
		# THIS SHOULD BE AUTO-GENERATED..! :(
		self.ui.buttonBox.accepted.connect(self.accept)
		self.ui.buttonBox.rejected.connect(self.reject)
		
		self.ui.importButton.clicked.connect(self.import_keys)
		self.ui.exportButton.clicked.connect(self.export_keys)
		
		stretch_table(self.ui.table, 2)
		qmenu(self.ui.table, self.show_key_submenu)
		
		self.loadKeys()
	
	def _insert_row(self, priv, pub, comment, icon=None):
		table = self.ui.table
		j = table.rowCount()
		table.insertRow(j)
			
		set_col(table, j, 0, priv)
		set_col(table, j, 1, pub)
		set_col(table, j, 2, comment, icon=icon)
	
	def loadKeys(self):
		k = self.iso.store.keyStorage
		blind = self.iso.store.blindStorage
		blindacc = self.iso.store.blindAccountStorage
		accstore = self.iso.store.accountStorage
		table = self.ui.table
		icon_a = qicon(":/icons/images/account.png")
		icon_b = qicon(":/icons/images/account_suit.png")
		icon_bt = qicon(":/op/images/op/blind_transfer.png")
		icon_bt_spent = qicon(":/op/images/op/transfer_to_blind.png")
		#icon_bt_un = qicon(":/op/images/op/transfer_from_blind.png")
		j = -1
		for pub in k:
			j += 1
			comment = ""
			icon = None
			try:
				priv = self.iso.getPrivateKeyForPublicKeys([pub])[0]
			except Exception as e:
				priv = "BROKEN: " + str(e)
			
			try:
				accname = self.iso.getAccountFromPublicKey(pub)
				comment = accname
				icon = icon_a
				acc = self.iso.getAccount(accname, force_remote=True)
				kt = self.iso.bts.wallet.getKeyType(acc, pub)
				comment += ", " + kt + " key"
			except:
				pass
			
			if not(comment):
				blacc = blindacc.getByPublicKey(pub)
				if blacc:
					comment = blacc["label"]
					icon = icon_b
			
			if not(comment):
				ble = blind.getEntriesBy([("pub_to", pub),("pub_from", pub),("pub_child",pub)], False)
				for e in ble:
					icon = icon_bt
					comment = "blind transfer"
					if not(e["pub_to"]):
						comment = "transfer from blind"
						icon = icon_bt_spent
					if e["used"]:
						comment += ", spent"
						icon = icon_bt_spent
					break
			
			self._insert_row(priv, pub, comment, icon=icon)
	
	def export_keys(self):
		wallet_name = "wallet"
		path, _ = QtGui.QFileDialog.getSaveFileName(self, 'Export Private Keys', wallet_name + "_keys.json", "key dump (*.json)")
		if not path:
			return False
		
		array = [ ]
		
		table = self.ui.table
		for j in range(0, table.rowCount()):
			priv = table.item(j, 0).text()
			pub = table.item(j, 1).text()
			if priv.startswith("BROKEN: "):
				continue
			array.append( [ pub, priv ] )
		
		data = json.dumps(array)
		try:
			with open(path, "w") as f:
				f.write(data)
		except Exception as exc:
			showexc(exc)
			return False
		return True
		
	def import_keys(self):
		path, _ = QtGui.QFileDialog.getOpenFileName(self, 'Import key dump file', '', "key dump (*.json)")
		if not path:
			return False
		
		try:
			with open(path, "r") as f:
				data = f.read()
		except Exception as exc:
			showexc(exc)
			return False
		
		try:
			array = json.loads(data)
		except Exception as exc:
			showexc(exc)
			return False
		
		import bitshares.exceptions
		npub = [ ]
		for pair in array:
			try:
				pub, priv = pair
			except Exception as exc:
				showerror("JSON data in wrong format: " + str(exc))
				return False
			
			try:
				self.iso.bts.wallet.addPrivateKey(priv)
				npub.append( pub )
				self._insert_row(priv, pub, "")
			except bitshares.exceptions.KeyAlreadyInStoreException:
				pass
			except Exception as exc:
				showexc(exc)
				return False
		
		n = len(npub)
		self._ret += n
		showdialog("Added %d keys" % n)
		return True
	
	def show_key_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Copy Private Key", self._copy_priv)
		qaction(self, menu, "Copy Public Key", self._copy_pub)
		qaction(self, menu, "Copy Name", self._copy_name)
		qmenu_exec(self.ui.table, menu, position)
		
	
	def _copy_col(self, col):
		table = self.ui.table
		j = table_selrow(table)
		if j <= -1: return
		val = table.item(j, col).text()
		if not len(val.strip()):
			return
		if col == 2 and "," in val: # hack -- cut out name
			val, _ = val.split(",")
		qclip(val)
	
	def _copy_priv(self):
		return self._copy_col(0)
	def _copy_pub(self):
		return self._copy_col(1)
	def _copy_name(self):
		return self._copy_col(2)
	
