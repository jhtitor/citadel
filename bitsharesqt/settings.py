from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.settings import Ui_SettingsWindow

from .remotes import RemotesEditor

from .utils import *
import json

import logging
log = logging.getLogger(__name__)

def upstr(val):
	return str(val).upper()
def downstr(val):
	return str(val).lower()

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
		
		self.linked_elements = [ ]
		
		self._link_settingc(self.ui.sellFOK, 'order-fillorkill')
		self._link_setting(self.ui.sellExpireEdit, 'order-expiration', deltainterval, 3600*24, deltasec)
		app().mainwin.uiExpireSliderLink(self.ui.sellExpireEdit, self.ui.sellExpireSlider, emit=True)
		self._link_settingc(self.ui.advancedmodeEnabled, 'ui_advancedmode')
		
		self._update_static()
		
		self._link_settingc(self.ui.autoConnect, 'autoconnect', bool, True)
		self._link_settingc(self.ui.cycleNodes, 'cyclenodes', bool, True)
		
		self._link_settingc(self.ui.proxyEnabled, 'proxy_enabled')
		self._link_settingc(self.ui.proxyAuth, 'proxy_auth_enabled')
		self._link_setting(self.ui.proxyType, 'proxy_type', cons=upstr, decons=downstr)
		self._link_setting(self.ui.proxyHost, 'proxy_host')
		self._link_setting(self.ui.proxyPort, 'proxy_port', int, "", int)
		self._link_setting(self.ui.proxyUser, 'proxy_user')
		self._link_setting(self.ui.proxyPass, 'proxy_pass')
		
		self.ui.proxyAuth.stateChanged.connect(self.display_proxy_settings)
		self.display_proxy_settings(self.ui.proxyAuth.checkState())
		
		self.ui.serverList.itemSelectionChanged.connect(self.select_node)
		stretch_table(self.ui.serverList)
		self.relist_nodes()
		
	
	def setPage(self, page):
		self.ui.tabWidget.setCurrentIndex(page)

	
	def restore_defaults(self):
		ok = askyesno("Restore default settings?")
		if ok:
			self.iso.store.wipeConfig()
			self.iso.bootstrap_wallet(wipe=True)
			self._update_linked()
			self._update_static()
			self.relist_nodes()
	
	def display_proxy_settings(self, cs):
		ws = [ self.ui.proxyUser, self.ui.proxyPass,
			self.ui.proxyUserLabel, self.ui.proxyPassLabel ]
		for widget in ws:
			widget.setVisible(bool(cs))
	
	def _update_static(self):
		config = self.iso.bts.config
		self.ui.nodeLabel.setText(str(config["node"]))
	
	def _update_elem(self, elem):
		config = self.iso.bts.config
		name, cons, decons, defl = elem._pyUserData
		val = defl
		try:
			if not(config[name] is None):
				val = cons(config[name])
		except:
			log.exception("Could not read config %s" % name)
		#print("Updating elem", elem.objectName(), "setting value", val)
		set_value(elem, val)

	def _update_linked(self):
		for elem in self.linked_elements:
			self._update_elem(elem)

	def _link_settingc(self, elem, name, cons=bool, defl=False, decons=int):
		elem._pyUserData = name, cons, decons, defl
		self._update_elem(elem)
		elem.stateChanged.connect(self._setting_updatec)
		self.linked_elements.append(elem)

	def _link_setting(self, elem, name, cons=str, defl="", decons=str):
		elem._pyUserData = name, cons, decons, defl
		self._update_elem(elem)
		any_change(elem, self._setting_update, progress=False)
		self.linked_elements.append(elem)

	def _setting_update(self):
		config = self.iso.bts.config
		elem = self.sender()
		name, cons, decons, defl = elem._pyUserData
		try:
			val = decons( any_value(elem) )
			config[name] = val
			#print("Wrote config", name, val, type(val))
		except:
			log.exception("Could not write config %s" % name)

	def _setting_updatec(self, cs):
		config = self.iso.bts.config
		elem = self.sender()
		name, cons, decons, defl = elem._pyUserData
		val = decons( cs )
		config[name] = val
		#print("Wrote config", name, val, type(val))

	def select_node(self):
		config = self.iso.bts.config
		table = self.ui.serverList
		
		items = table.selectedItems()
		if len(items) < 1:
			return
		
		item = items[1]
		
		config["node"] = str(item.text())
		self.ui.nodeLabel.setText(str(config["node"]))

	def edit_nodes(self):
		win = RemotesEditor(rtype=RemotesEditor.RTYPE_BTS_NODE, isolator=self.iso)
		win.exec_()
		self.relist_nodes()

	def edit_gateways(self):
		win = RemotesEditor(rtype=RemotesEditor.RTYPE_BTS_GATEWAY, isolator=self.iso)
		win.exec_()

	def edit_faucets(self):
		win = RemotesEditor(rtype=RemotesEditor.RTYPE_BTS_FAUCET, isolator=self.iso)
		win.exec_()


	def relist_nodes(self):
		store = self.iso.store.remotesStorage
		table = self.ui.serverList
		
		table.blockSignals(True)
		table.setRowCount(0)
		
		remotes = store.getRemotes(store.RTYPE_BTS_NODE)
		for remote in remotes:
			
			j = table.rowCount()
			table.insertRow(j)
			
			set_col(table, j, 0, str(remote['label']), data=remote['id'])
			set_col(table, j, 1, str(remote['url']), data=remote['id'] )
		
		table.blockSignals(False)
	