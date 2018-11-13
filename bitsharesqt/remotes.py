from PyQt5 import QtCore, QtGui, QtWidgets

from uidef.remotes import Ui_RemotesWindow
from .utils import *
import logging
log = logging.getLogger(__name__)

import json

from rpcs import gateway_apis

class RemotesEditor(QtWidgets.QDialog):
	
	RTYPE_BTS_NODE = 0
	RTYPE_BTS_GATEWAY = 1
	RTYPE_BTS_FAUCET = 2
	
	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('isolator', None)
		self.rtype = kwargs.pop('rtype', 0)
		self.class_edit = bool(self.rtype == RemotesEditor.RTYPE_BTS_GATEWAY)
		super(RemotesEditor, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_RemotesWindow()
		
		ui.setupUi(self)
		
		self.ui.closeButton.clicked.connect(self.accept)
		
		self.ui.addButton.clicked.connect(self.add_empty)
		self.ui.delButton.clicked.connect(self.del_selected)
		
		self.ui.tableWidget.itemChanged.connect(self.edit_item)
		
		if not(self.class_edit):
			self.ui.tableWidget.setColumnCount(2)
		stretch_table(self.ui.tableWidget, col=1)
		
		
		self.merge()
	
	def del_selected(self):
		store = self.iso.store.remotesStorage
		table = self.ui.tableWidget
		
		items = table.selectedItems()
		
		rows = set()
		for item in items:
			rows.add(item.row())
		
		n = table.rowCount()
		for j in range(0, n):
			l = n - j - 1
			if l in rows:
				c1 = table.item(l, 0)
				id = c1.data(99)
				store.delete(id)
				cb = table.cellWidget(l, 2)
				if cb:
					cb.currentIndexChanged.disconnect(self._edit_cb)
				table.removeRow(l)
	
	def edit_item(self, item):
		store = self.iso.store.remotesStorage
		table = self.ui.tableWidget
		
		j = item.row()
		
		c1 = table.item(j, 0)
		c2 = table.item(j, 1)
		cb = table.cellWidget(j, 2)
		
		id = c1.data(99)
		
		store.update(id, "label", c1.text() )
		store.update(id, "url", c2.text() )
		if cb:
			store.update(id, "ctype", cb.currentText() )
	
	def _edit_cb(self):
		table = self.ui.tableWidget
		row = table.currentIndex()
		item = table.item(row.row(), 0)
		self.edit_item(item)
	
	def add_empty(self):
		store = self.iso.store.remotesStorage
		table = self.ui.tableWidget
		
		newid = store.add(self.rtype, "", "", "", "")
		
		table.blockSignals(True)
		
		j = table.rowCount()
		table.insertRow(j)
		
		set_col(table, j, 0, "New node", data=newid)
		set_col(table, j, 1, "wss://"  , data=newid)
		
		if self.class_edit:
			cb = self._gateway_class_cb()
			on_combo(cb, self._edit_cb)
			table.setCellWidget(j, 2, cb)
		
		table.blockSignals(False)
	
	def _gateway_class_cb(self):
		cb = QtWidgets.QComboBox()
		for gw in gateway_apis:
			set_combo(cb, str(gw), force=True)
		if len(gateway_apis):
			set_combo(cb, str(gateway_apis[0]))
		return cb

	def merge(self):
		store = self.iso.store.remotesStorage
		table = self.ui.tableWidget
		
		table.blockSignals(True)
		
		remotes = store.getRemotes(self.rtype)
		for remote in remotes:
			
			j = table.rowCount()
			table.insertRow(j)
			
			set_col(table, j, 0, str(remote['label']), data=remote['id'])
			set_col(table, j, 1, str(remote['url']),   data=remote['id'])
			
			if self.class_edit:
				cb = self._gateway_class_cb()
				set_combo(cb, remote['ctype'])
				on_combo(cb, self._edit_cb)
				table.setCellWidget(j, 2, cb)
			
		table.blockSignals(False)
	