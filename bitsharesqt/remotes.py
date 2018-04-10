from PyQt4 import QtCore, QtGui

from uidef.remotes import Ui_RemotesWindow
from .utils import *
import logging
log = logging.getLogger(__name__)

import json

class RemotesEditor(QtGui.QDialog):
	
	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('isolator', None)
		self.rtype = kwargs.pop('rtype', 0)
		super(RemotesEditor, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_RemotesWindow()
		
		ui.setupUi(self)
		
		self.ui.closeButton.clicked.connect(self.accept)
		
		#self.ui.editnodesButton.clicked.connect(self.edit_nodes)
		
		#fb = self.ui.faucetBox
		#for name, url, refurl, factory in KnownFaucets:
		#	fb.addItem(name, (url, refurl))
		
		self.ui.addButton.clicked.connect(self.add_empty)
		self.ui.delButton.clicked.connect(self.del_selected)
		
		self.ui.tableWidget.itemChanged.connect(self.edit_item)
		
		stretch_table(self.ui.tableWidget)
		
		
		self.merge()
	
	def del_selected(self):
		store = self.iso.store.remotesStorage
		table = self.ui.tableWidget
		
		items = table.selectedItems()
		
		rows = set()
		for item in items:
			rows.add(item.row());
		
		n = table.rowCount()
		for j in range(0, n):
			l = n - j - 1
			if l in rows:
				c1 = table.item(l, 0)
				id = c1.data(99)
				store.delete(id)
				table.removeRow(l)
	
	def edit_item(self, item):
		store = self.iso.store.remotesStorage
		table = self.ui.tableWidget
		
		j = item.row()
		
		c1 = table.item(j, 0)
		c2 = table.item(j, 1)
		
		id = c1.data(99)
	
		store.update(id, "label", c1.text() )
		store.update(id, "url", c2.text() )
	
	def add_empty(self):
		store = self.iso.store.remotesStorage
		table = self.ui.tableWidget
		
		newid = store.add(self.rtype, "", "", "")
		
		j = table.rowCount()
		table.insertRow(j)
		
		table.blockSignals(True)
		
		table.setItem(j, 0, QtGui.QTableWidgetItem("New node") )
		table.setItem(j, 1, QtGui.QTableWidgetItem("wss://") )
		
		c1 = table.item(j, 0)
		c2 = table.item(j, 1)
		c1.setData(99, newid)
		c2.setData(99, newid)
		
		table.blockSignals(False)
	
	def merge(self):
		store = self.iso.store.remotesStorage
		table = self.ui.tableWidget
		
		table.blockSignals(True)
		
		remotes = store.getRemotes(self.rtype)
		for remote in remotes:
			
			j = table.rowCount()
			table.insertRow(j)
			
			table.setItem(j, 0, QtGui.QTableWidgetItem( str(remote['label']) ))
			table.setItem(j, 1, QtGui.QTableWidgetItem( str(remote['url']) ))
			
			c1 = table.item(j, 0)
			c2 = table.item(j, 1)
			c1.setData(99, remote['id'])
			c2.setData(99, remote['id'])
			
		table.blockSignals(False)
	