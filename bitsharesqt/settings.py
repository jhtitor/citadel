from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.settings import Ui_SettingsWindow

from .remotes import RemotesEditor

from .utils import *

import json

import logging
log = logging.getLogger(__name__)

class SettingsWindow(QtWidgets.QDialog):

	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('isolator', None)
		super(SettingsWindow, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_SettingsWindow()

		ui.setupUi(self)

		self.ui.closeButton.clicked.connect(self.accept)
		
		self.ui.restoredefaultsButton.clicked.connect(self.restore_defaults)
		
		self.ui.editnodesButton.clicked.connect(self.edit_nodes)
		self.ui.editgatewaysButton.clicked.connect(self.edit_gateways)
		self.ui.editfaucetsButton.clicked.connect(self.edit_faucets)
		
		#fb = self.ui.faucetBox
		#for name, url, refurl, factory in KnownFaucets:
		#	fb.addItem(name, (url, refurl))
		
		self._link_settingc(self.ui.sellFOK, 'order-fillorkill')
		self._link_setting(self.ui.sellExpireEdit, 'order-expiration', deltainterval, 3600*24, deltasec)
		app().mainwin.uiExpireSliderLink(self.ui.sellExpireEdit, self.ui.sellExpireSlider, emit=True)
		self._link_settingc(self.ui.advancedmodeEnabled, 'ui_advancedmode')
		
		config = self.iso.bts.config
		
		self.ui.nodeLabel.setText(str(config["node"]))
		#self.ui.autoConnect.setChecked(True if config["proxy_enabled"] else False)
		
		self._link_settingc(self.ui.autoConnect, 'autoconnect')
		
		self._link_settingc(self.ui.proxyEnabled, 'proxy_enabled')
		self._link_settingb(self.ui.proxyType, 'proxy_type')
		self._link_setting(self.ui.proxyHost, 'proxy_host')
		self._link_setting(self.ui.proxyPort, 'proxy_port', int, "")
		
		
		self.ui.serverList.itemSelectionChanged.connect(self.select_node)
		stretch_table(self.ui.serverList)
		self.relist_nodes()

	def setPage(self, page):
		self.ui.tabWidget.setCurrentIndex(page)

	
	def restore_defaults(self):
		ok = askyesno("Restore default settings?")
		if ok:
			config = self.iso.bts.config
			config.wipe()
			self.iso.bootstrap_wallet(wipe=True)

	def _link_settingc(self, elem, name, cons=bool, defl=False):
		config = self.iso.bts.config
		if config[name]:
			val = cons(config[name])
		else:
			val = defl
		elem.setChecked(val)
		elem._pyUserData = name, bool
		elem.stateChanged.connect(self._setting_updatec)

	def _link_settingb(self, elem, name, cons=str, defl=""):
		config = self.iso.bts.config
		val = cons(config[name])
		if not config[name]:
			val = defl
		set_combo(elem, val.upper())
		elem._pyUserData = name, str
		elem.currentIndexChanged.connect(self._setting_updateb)

	def _link_setting(self, elem, name, cons=str, defl="", decons=str):
		config = self.iso.bts.config
		if not config[name]:
			val = defl
		else:
			val = cons(config[name])
		elem.setText(str(val))
		elem._pyUserData = name, decons
		elem.editingFinished.connect(self._setting_update)

	def _setting_update(self):
		config = self.iso.bts.config
		elem = self.sender()
		name, decons = elem._pyUserData
		config[name] = decons( elem.text() )

	def _setting_updatec(self, cs):
		config = self.iso.bts.config
		elem = self.sender()
		name, decons = elem._pyUserData
		config[name] = bool(cs)

	def _setting_updateb(self, cs):
		config = self.iso.bts.config
		elem = self.sender()
		name, decons = elem._pyUserData
		config[name] = elem.currentText().lower()

	def select_node(self):
		config = self.iso.bts.config
		table = self.ui.serverList
		
		items = table.selectedItems()
		if len(items) < 1:
			return
		
		item = items[1]
		id = item.data(99)
		
		#entry = store.getEntry(id)
		
		config["node"] = str(item.text())
		self.ui.nodeLabel.setText(str(config["node"]))

	def edit_nodes(self):
		win = RemotesEditor(rtype=0, isolator=self.iso)
		win.exec_()
		self.relist_nodes()

	def edit_gateways(self):
		win = RemotesEditor(rtype=1, isolator=self.iso)
		win.exec_() 

	def edit_faucets(self):
		win = RemotesEditor(rtype=2, isolator=self.iso)
		win.exec_() 


	def relist_nodes(self):
		store = self.iso.store.remotesStorage
		table = self.ui.serverList
		
		table.blockSignals(True)
		table.setRowCount(0)
		
		remotes = store.getRemotes(0)
		for remote in remotes:
			
			j = table.rowCount()
			table.insertRow(j)
			
			table.setItem(j, 0, QtGui.QTableWidgetItem( str(remote['label']) ))
			table.setItem(j, 1, QtGui.QTableWidgetItem( str(remote['url']) ))

			c1 = table.item(j, 0)
			if not c1:
				print("Inserted nothing?!", j, remote)
				continue
			c2 = table.item(j, 1)
			c1.setData(99, remote['id'])
			c2.setData(99, remote['id'])
			
		table.blockSignals(False)

	#def generate_password(self):
	#	pass