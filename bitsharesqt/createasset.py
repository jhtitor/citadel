from PyQt4 import QtCore, QtGui
from uidef.createasset import Ui_CreateAsset

from .utils import *
import logging
log = logging.getLogger(__name__)
import json

from .transactionbuilder import QTransactionBuilder
from bitsharesbase.asset_permissions import asset_permissions
from bitsharesbase.asset_permissions import todict

class AssetWindow(QtGui.QDialog):
	
	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('isolator', None)
		self.accounts = kwargs.pop('accounts', [ ])
		self.activeAccount = kwargs.pop('account', None)
		self.mode = kwargs.pop('mode', "create")
		self.asset = kwargs.pop('asset', None)
		super(AssetWindow, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_CreateAsset()
		
		ui.setupUi(self)
		
		for account_name in self.accounts:
			self.ui.accountBox.addItem(account_name)
			self.ui.transferFromAccount.addItem(account_name) # keep
			self.ui.untransferFromAccount.addItem(account_name) # those
		mw = app().mainwin
		mw.uiAccountAssetLink(self.ui.accountBox, self.ui.feeAsset)
		mw.uiAccountAssetLink(self.ui.transferFromAccount, self.ui.transferFeeAsset)
		mw.uiAccountAssetLink(self.ui.untransferFromAccount, self.ui.untransferFeeAsset)
		
		if not(mw.is_advancedmode()):
			hide = [ self.ui.feeAsset, self.ui.feeAssetLabel,
			self.ui.transferFeeAsset, self.ui.transferFeeLabel,
			self.ui.untransferFeeAsset, self.ui.untransferFeeLabel ]
			for w in hide:
				w.hide()
		
		i = 0
		for name, flag in asset_permissions.items():
			item = QtGui.QListWidgetItem(name)
			item.setData(32, i)
			item.setData(33, name)
			item.setData(34, flag)
			#item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
			item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
			item.setCheckState(QtCore.Qt.Unchecked)
			self.ui.permList.addItem(item)
			
			item = QtGui.QListWidgetItem(name)
			item.setData(32, i)
			item.setData(33, name)
			item.setData(34, flag)
			item.setFlags(QtCore.Qt.ItemIsUserCheckable)
			item.setCheckState(QtCore.Qt.Unchecked)
			self.ui.flagList.addItem(item)
			item.setHidden(True)
			
			i += 1
		
		self.ui.permList.itemChanged.connect(self.permission_click)
		
		self.ui.isBitasset.stateChanged.connect(self.bitasset_toggle)
		
		self.ui.buttonBox.clicked.connect(self.route_buttonbox)
		
		self.setupMode(self.mode)
		
		if self.asset:
			self.setupAsset(self.asset)
		else:
			set_combo(self.ui.accountBox, self.activeAccount["name"])
			self.bitasset_toggle(0)
		
		#self.ui.createButton.clicked.connect(self.reject)
		#self.ui.readButton.clicked.connect(self.read_memo)
		#self.ui.signButton.clicked.connect(self.sign_memo)
	
	def bitasset_toggle(self, state):
		self.ui.frameBitasset.setEnabled(bool(state))
		self.ui.isPredictionMarket.setEnabled(bool(state))
	
	def route_buttonbox(self, button):
#		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Apply):
		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Ok):
			if self.mode == "create":
				self.attempt_create()
			if self.mode == "edit":
				self.attempt_update()
			if self.mode == "bitasset":
				self.attempt_update()
			if self.mode == "issue":
				self.make_transfer()
			if self.mode == "reserve":
				self.make_reserve()
			if self.mode == "fund":
				self.make_fund()
		
		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Cancel):
			self.reject()
		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Close):
			self.reject()
	
	def setupAsset(self, asset):
		self.ui.symbolEdit.setText(asset["symbol"])
		self.ui.precisionEdit.setText(str(asset["precision"]))
		self.ui.totalEdit.setText(str(asset["options"]["max_supply"] / pow(10, asset["precision"])))
		set_combo(self.ui.transferAsset, asset["symbol"])
		set_combo(self.ui.untransferAsset, asset["symbol"])
		
		self.ui.symbolEdit.setEnabled(False)
		self.ui.precisionEdit.setEnabled(False)
		self.ui.totalEdit.setEnabled(False)
		self.ui.permList.setEnabled(False)
		
		self.ui.descriptionPlain.setPlainText(asset["options"]["description"])
		
		self.ui.marketFee.setValue(int(asset["options"]["market_fee_percent"]))
		cer = asset["options"]["core_exchange_rate"]
		print(asset["symbol"], cer)
		rate = (int(cer["base"]["amount"])/pow(10, 5)) / (int(cer["quote"]["amount"])/pow(10, asset["precision"]))
		self.ui.coreExchangeRate.setMaximum(1000000000000) # ?
		self.ui.coreExchangeRate.setDecimals(5) # BTS 5 - TODO: unhardcode?
		self.ui.coreExchangeRate.setValue(float(rate))
		
		perm_dict = todict(asset["options"]["issuer_permissions"])
		flag_dict = todict(asset["options"]["flags"])
		i = 0
		for k, v in perm_dict.items():
			self.ui.permList.item(i).setCheckState(QtCore.Qt.Checked if v else QtCore.Qt.Unchecked)
			i += 1
		i = 0
		for k, v in flag_dict.items():
			self.ui.flagList.item(i).setCheckState(QtCore.Qt.Checked if v else QtCore.Qt.Unchecked)
			i += 1
		issuer = asset["issuer"]
		if not self.iso.offline:
			asset.refresh()
			try:
				issuer = self.iso.getAccount(issuer)
				issuer = issuer["name"]
			except:
				pass
		
		# Issue
		self.ui.transferAmount.setDecimals(asset["precision"])
		self.ui.transferAmount.setMaximum(
		int(asset["options"]["max_supply"]) / pow(10, asset["precision"]))
#		self.ui.transferFromAccount.setEnabled(True)
		set_combo(self.ui.transferFromAccount, issuer)
#		self.ui.transferFromAccount.setEnabled(False)
		
		# Reserve
		self.ui.untransferAmount.setDecimals(asset["precision"])
		self.ui.untransferAmount.setMaximum(
		int(asset["options"]["max_supply"]) / pow(10, asset["precision"]))
#		self.ui.untransferFromAccount.setEnabled(True)
#		set_combo(self.ui.untransferFromAccount, issuer)
#		self.ui.untransferFromAccount.setEnabled(False)
		
		set_combo(self.ui.accountBox, issuer)
		self.ui.accountBox.setEnabled(False)
		
		# BitAsset
		self.ui.isBitasset.setEnabled(False)
		if asset.is_bitasset:#["bitasset"]:
			#asset.full = True
			#asset.refresh()
			bitasset = asset["bitasset_data"]
			options = bitasset["options"]
			from pprint import pprint
			pprint(options)
			self.ui.isBitasset.setCheckState(1)
			self.ui.feedLifetime.setValue(options["feed_lifetime_sec"])
			self.ui.forceSettlementDelay.setValue(options["force_settlement_delay_sec"])
			self.ui.forceSettlementOffset.setValue(options["force_settlement_offset_percent"])
			self.ui.maxForceSettlement.setValue(options["maximum_force_settlement_volume"])
			self.ui.minimumFeeds.setValue(options["minimum_feeds"])
			self.ui.backingAsset.setText(options["short_backing_asset"])
			if "is_prediction_market" in asset and asset["is_prediction_market"]:
				self.ui.isPredictionMarket.setCheckState(1)
			if "is_prediction_market" in asset["options"] and asset["options"]["is_prediction_market"]:
				self.ui.isPredictionMarket.setCheckState(1)
		else:
			self.ui.isBitasset.setCheckState(0)
			self.ui.isPredictionMarket.setVisible(False)
			self.ui.frameBitasset.setVisible(False)
	
	def setupMode(self, mode):
		if mode == "create":
			self.hideTabs([5, 4, 3])
			self.showTab(0)
		if mode == "edit":
			self.hideTabs([5, 4, 3])
			self.showTab(0)
		if mode == "bitasset":
			self.hideTabs([5, 4, 3])
			self.showTab(2)
		if mode == "issue":
			self.hideTabsX(3)
		if mode == "reserve":
			self.hideTabsX(4)
		if mode == "fund":
			self.hideTabsX(4)
			self.ui.tabWidget.setTabText(0, "Fund Fee Pool")
	
	
	def showTab(self, i):
		self.ui.tabWidget.setCurrentIndex(i)
	
	def hideTabs(self, inds):
		for i in inds:
			self.ui.tabWidget.removeTab(i)
	
	def hideTabsX(self, xindex):
		for i in range(5, -1, -1):
			if i != xindex:
				self.ui.tabWidget.removeTab(i)
	
	def permission_click(self, item):
		row = item.data(32)
		rel_item = self.ui.flagList.item(row)
		if item.checkState():
			rel_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
			rel_item.setHidden(False)
		else:
			rel_item.setCheckState(0)
			rel_item.setFlags(QtCore.Qt.ItemIsUserCheckable)
			rel_item.setHidden(True)
	
	def collect_flags(self, elem):
		d = { }
		n = elem.count()
		for i in range(0, n):
			item = elem.item(i)
			name = item.data(33)
			if item.checkState():
				d[name] = True
			else:
				d[name] = False
		return d
	
	def prev_options(self):
		pm = False
		if "is_prediction_market" in self.asset:
			pm = self.asset["is_prediction_market"]
		return {
		"symbol": self.asset["symbol"],
		"issuer": self.asset["issuer"],
		
		"precision": self.asset["precision"],
		"max_supply": int(self.asset["options"]["max_supply"]),
		"core_exchange_rate": self.asset["options"]["core_exchange_rate"],
		
		"new_issuer": self.asset["issuer"],
		"permissions": todict(self.asset["options"]["issuer_permissions"]),
		"flags": self.asset["flags"],
		"description": self.asset["description"],
		"is_prediction_market": pm,
		"market_fee_percent": self.asset["options"]["market_fee_percent"],
		}
	def prev_bitoptions(self):
		options = self.asset["bitasset_data"]["options"]
		return {
		"symbol": self.asset["symbol"],
		"issuer": self.asset["issuer"],
		
		"feed_lifetime_sec": options["feed_lifetime_sec"],
		"force_settlement_delay_sec": options["force_settlement_delay_sec"],
		"force_settlement_offset_percent": options["force_settlement_offset_percent"],
		"maximum_force_settlement_volume": options["maximum_force_settlement_volume"],
		"minimum_feeds": options["minimum_feeds"],
		"short_backing_asset": options["short_backing_asset"],
		}
	
	def collect_options(self):
		issuer = self.ui.accountBox.currentText()
		try:
			issuer = self.iso.getAccount(issuer)
			issuer = issuer["id"]
		except:
			pass
		precision = int(self.ui.precisionEdit.text())
		rate = float(self.ui.coreExchangeRate.value())
		cer = { "base": { "amount": 0, "asset_id": "1.3.0" },
			"quote": { "amount": 0, "asset_id": "1.3.1" } }
		if rate < 1:
			cer["quote"]["amount"] = 1 * pow(10, precision)
			cer["base"]["amount"] = 1/rate * pow(10, 5)
		else:
			cer["quote"]["amount"] = 1 * pow(10, 5)
			cer["base"]["amount"] = rate * pow(10, precision)
		return {
		"symbol": self.ui.symbolEdit.text(),
		"issuer": issuer,
		
		"precision": precision,
		"max_supply": int(float(self.ui.totalEdit.text()) * pow(10, precision)),
		"core_exchange_rate": cer,
		
		"new_issuer": issuer,
		"permissions": self.collect_flags(self.ui.permList),
		"flags": self.collect_flags(self.ui.flagList),
		"description": self.ui.descriptionPlain.toPlainText(),
		"is_prediction_market": bool(self.ui.isPredictionMarket.checkState()),
		"market_fee_percent": self.ui.marketFee.value(),
		}
	
	def collect_bitoptions(self):
		if not(self.ui.isBitasset.checkState()):
			return None
		issuer = self.ui.accountBox.currentText()
		try:
			issuer = self.iso.getAccount(issuer)
			issuer = issuer["id"]
		except:
			pass
		return {
		"symbol": self.ui.symbolEdit.text(),
		"issuer": issuer,
		
		"feed_lifetime_sec": self.ui.feedLifetime.value(),
		"force_settlement_delay_sec": self.ui.forceSettlementDelay.value(),
		"force_settlement_offset_percent": self.ui.forceSettlementOffset.value(),
		"maximum_force_settlement_volume": self.ui.maxForceSettlement.value(),
		"minimum_feeds": self.ui.minimumFeeds.value(),
		"short_backing_asset": self.ui.backingAsset.text()
		}
	
	def attempt_create(self):
		fee_asset = anyvalvis(self.ui.feeAsset, None)#.currentText()
		
		options = self.collect_options()
		options["permissions"] = self.collect_flags(self.ui.permList)
		options["flags"] = self.collect_flags(self.ui.flagList)
		options.pop("new_issuer")
		
		bit_options = self.collect_bitoptions()
		
		if options["permissions"]["disable_force_settle"] or options["permissions"]["global_settle"]:
			if not bit_options:
				showerror("Assets with `disable_force_settle` or `global_settle` permissions MUST be Market-issued BitAssets")
				return False
		
		r = QTransactionBuilder.QCreateAsset(
			bitasset_options=bit_options,
			fee_asset=fee_asset,
			
			isolator=self.iso,
			**options
		)
		
		if r:
			self.accept()
		#print("QCreateAsset:", r)
	
	def attempt_update(self):
		fee_asset = anyvalvis(self.ui.feeAsset, None)#.currentText()
		
		vs = [ ]
		
		prev_options = self.prev_options()
		options = self.collect_options()
		if not(dict_same(prev_options, options)):
			options.pop("permissions")
			options.pop("precision")
			options.pop("max_supply")
			v1 = QTransactionBuilder.VUpdateAsset(
				*options,
				fee_asset=fee_asset,
				isolator=self.iso
			)
			vs.append( v1 )
		
		bitoptions = self.collect_bitoptions()
		if bitoptions:
			prev_bitoptions = self.prev_bitoptions()
			if not(dict_same(prev_bitoptions, bitoptions)):
				v2 = QTransactionBuilder.VUpdateBitAsset(
					*bitoptions,
					isolator=self.iso
				)
				vs.append( v2 )
		
		if len(vs) < 1:
			showmsg("No change")
			self.reject()
			return
		
		r = QTransactionBuilder._QExecS(self.iso, vs)
		if r:
			self.accept()
	
	def make_transfer(self):
		account_from = self.ui.transferFromAccount.currentText()
		account_to = self.ui.transferToAccount.currentText()
		asset_name = self.ui.transferAsset.currentText()
		asset_amount = self.ui.transferAmount.text()
		memo_text = self.ui.transferMemo.toPlainText()
		fee_asset = anyvalvis(self.ui.transferFeeAsset, None)#.currentText()
		
		try:
			trx = QTransactionBuilder.QIssueAsset(
				asset_name,
				asset_amount,
				account_from,
				account_to,
				memo=memo_text,
				fee_asset=fee_asset,
				isolator=self.iso)
		except BaseException as error:
			showexc(error)
			return False
		self.accept()
		return True
	
	def make_reserve(self):
		account_from = self.ui.untransferFromAccount.currentText()
		asset_name = self.ui.untransferAsset.currentText()
		asset_amount = self.ui.untransferAmount.text()
		fee_asset = anyvalvis(self.ui.untransferFeeAsset, None)#.currentText()
		
		try:
			trx = QTransactionBuilder.QReserveAsset(
				asset_name,
				asset_amount,
				account_from,
				fee_asset=fee_asset,
				isolator=self.iso)
		except BaseException as error:
			showexc(error)
			return False
		
		self.accept()
		return True
	
	def make_fund(self):
		account_from = self.ui.untransferFromAccount.currentText()
		asset_name = self.ui.untransferAsset.currentText()
		asset_amount = self.ui.untransferAmount.text()
		fee_asset = anyvalvis(self.ui.untransferFeeAsset, None)#.currentText()
		
		try:
			trx = QTransactionBuilder.QFundFeePool(
				asset_name,
				asset_amount,
				account_from,
				fee_asset=fee_asset,
				isolator=self.iso)
		except BaseException as error:
			showexc(error)
			return False
		
		self.accept()
		return True
