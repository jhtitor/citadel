from PyQt5 import QtCore, QtGui
from .dashboard import DashboardTab
from .accountwizard import AccountWizard

from .netloc import RemoteFetch
from .utils import *
import logging
log = logging.getLogger(__name__)

import json
import time


class WindowWithContacts(QtCore.QObject):
	
	def init_contacts(self):
		
		self.ui.contactTable.itemClicked.connect(self.show_contact)
		self.ui.contactTable.itemSelectionChanged.connect(self.show_contact)
		#self.ui.contactTable.itemActivated.connect(self.show_contact)
		#self.ui.contactTable.itemDoubleClicked.connect(self._contact_quick_transfer)
		
		stretch_table(self.ui.contactTable)
		
		self.ui.contactTable.itemChanged.connect(self.edit_contact_description)
		
		qmenu(self.ui.contactTable, self.show_contact_submenu)
		
		self.contact_grabber = RemoteFetch(manager=self.Requests)
		
		self.ui.contactAdd.clicked.connect(self.add_contact)
	
	def add_contact(self):
		name = self.ui.contactName.text().strip()
		if not name:
			showwarn("Enter BitShares account name or ID")
			self.ui.contactName.setFocus()
		
		self.contact_grabber.fetch(
			self._lookup_contact, self.iso, name,
			ready_callback = self._lookup_contact_after,
			error_callback = self._lookup_contact_error,
			ping_callback = self.refreshUi_ping,
			description = "Looking up account")
	
	def _lookup_contact(self, iso, name):
		acc = iso.getAccount(name, force_remote=True)
		
		keys = iso.countStoredPrivateKeys(name)
		
		return (iso, acc, keys)

	def _lookup_contact_after(self, i, args):
		(iso, acc, keys) = args
		
		iso.storeAccount(acc, keys=keys)
		acc["keys"] = keys
		acc["comment"] = ""
		
		if not acc['name'] in self.contact_names:
			self._insertContactRow(acc)
		
	def _lookup_contact_error(self, i, err):
		showexc(err)
	
	def _selected_contact(self):
		table = self.ui.contactTable
		j = table_selrow(table)
		if (j <= -1):
			return (-1, None, None)
		item = table.item(j, 0)
		if not item:
			return (-1, None, None)
		account_name = item.text()
		internal_id = item.data(99)
		return (j, account_name, internal_id)
	
	def show_contact(self):
		table = self.ui.contactTable
		(j, account_name, account_id) = self._selected_contact()
		if j <= -1: return
		
		iso = self.iso
		#store = iso.store.accountStorage
		#entry = store.getById(internal_id)
		#if not entry:
		#	return
		try:
			account = iso.getAccount(account_name, force_local=True)#entry["name"])
		except:
			return
		
		old = self.ui.dashHolder.layout().itemAt(0)
		if old:
			if hasattr(old, '_tags') and account_name in old._tags:
				old.resync()
				return
			old = old.widget()
			self.ui.dashHolder.layout().removeWidget(old)
			old.setParent(None)
		
		wid = DashboardTab(simplify=True, isolator=self.iso)
		wid._tags = [ account_name ]
		self.ui.dashHolder.layout().addWidget(wid)
		wid.openAccount(iso, account)
	
	def edit_contact_description(self, item):
		store = self.iso.store.accountStorage
		table = self.ui.contactTable
		
		j = item.row()
		#ritem = table.item(j, 1)
		
		name = table.item(j, 0).text()
		comment = table.item(j, 1).text()
		
		store.update(name, "comment", comment)
	
	def loadContacts(self):
		entries = self.iso.store.accountStorage.getContacts()
		
		table = self.ui.contactTable
		table.setRowCount(0)
		
		[ self._insertContactRow(h) for h in entries ]
	
	def _insertContactRow(self, acc):
		self.add_contact_name(acc["name"], acc["keys"])
		
		if acc["keys"] > 0:
			return
		
		table = self.ui.contactTable
		j = table.rowCount()
		
		icon = qicon(":/icons/images/account.png")
		
		table.blockSignals(True)
		table.insertRow(j)
		set_col(table, j, 0, acc["name"], data=acc['id'], editable=False, icon=icon)
		set_col(table, j, 1, acc["comment"] if acc["comment"] else "", editable=True)
		table.blockSignals(False)
		
	
	def show_contact_submenu(self, position):
		menu = QtGui.QMenu()
		#qaction(self, menu, "Activate as Account", self.activate_account)
		qaction(self, menu, "Quick Transfer...", self._contact_quick_transfer)
		qaction(self, menu, "Copy Name", self._contact_copy_name)
		qaction(self, menu, "Import as Account...", self._contact_import_keys)
		menu.addSeparator()
		qaction(self, menu, "Remove Contact", self._remove_contact)
		qmenu_exec(self.sender(), menu, position)
	
	def _contact_quick_transfer(self):
		(j, account_name, account_id) = self._selected_contact()
		if j <= -1: return
		#asset = self.iso.getAsset('BTS')
		toacc = self.iso.getAccount(account_name)
		self.FTransfer(account=True, to=toacc)

	def _contact_copy_name(self):
		(j, account_name, account_id) = self._selected_contact()
		if j <= -1: return
		qclip(account_name)

	def _contact_import_keys(self):
		(j, account_name, account_id) = self._selected_contact()
		if j <= -1: return
		account = self.iso.getAccount(account_name)
		win = AccountWizard(
			isolator=self.iso,
			active=account,
			importMode=account_name
		)
		if not win.exec_():
			return 0

	def _remove_contact(self):
		(j, account_name, account_id) = self._selected_contact()
		if j <= -1: return
		
		table = self.ui.contactTable
		try:
			self.iso.store.accountStorage.delete(account_name)
			#self.iso.store.accountStorage.update(account_name, "keys", 0)
			self.remove_contact_name(account_name)
			table.removeRow(j)
			
			#showmessage("Contact removed")
		except Exception as exc:
			showexc(exc)
	

