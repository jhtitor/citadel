from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.assetwindow import Ui_AssetWindow

from .netloc import RemoteFetch
from .utils import *
import json
import logging
log = logging.getLogger(__name__)

from .transactionbuilder import QTransactionBuilder
from bitsharesbase.asset_permissions import asset_permissions
from bitsharesbase.asset_permissions import todict
from bitshares.price import Price

# TODO: read from chain config
GRAPHENE_MAX_SHARE_SUPPLY = 1000000000000000
GRAPHENE_MIN_COLLATERAL_RATIO = 1001
GRAPHENE_MAX_COLLATERAL_RATIO = 32000

# Tab IDs
TID_MAIN = 0
TID_ADVANCED = 1
TID_BITASSET = 2
TID_FEEDS = 3
TID_ISSUE = 4
TID_OVERRIDE = 5
TID_RESERVE = 6
TID_FUND = 7
TID_UNFUND = 8
TID_CLAIM = 9
TID_PUBLISH = 10
TID_SETTLE = 11

SECONDARY_TABS = [TID_RESERVE, TID_ISSUE, TID_OVERRIDE,
TID_FUND, TID_UNFUND, TID_CLAIM, TID_PUBLISH, TID_SETTLE]
# NOTE: TID_FEEDS is not here

class AssetWindow(QtWidgets.QDialog):
	
	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('isolator', None)
		self.accounts = kwargs.pop('accounts', [ ])
		self.activeAccount = kwargs.pop('account', None)
		self.mode = kwargs.pop('mode', "create")
		self.asset = kwargs.pop('asset', None)
		self.contacts = kwargs.pop('contacts', [ ])
		super(AssetWindow, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_AssetWindow()
		
		ui.setupUi(self)
		
		mw = app().mainwin
		mw.uiAccountAssetLink(self.ui.accountBox, self.ui.feeAsset)
		mw.uiAccountAssetLink(self.ui.transferFromAccount, self.ui.transferFeeAsset)
		mw.uiAccountAssetLink(self.ui.untransferFromAccount, self.ui.untransferFeeAsset)
		mw.uiAccountAssetLink(self.ui.fundAccount, self.ui.fundFeeAsset)
		mw.uiAccountAssetLink(self.ui.unfundAccount, self.ui.unfundFeeAsset)
		mw.uiAccountAssetLink(self.ui.claimAccount, self.ui.claimFeeAsset)
		mw.uiAccountAssetLink(self.ui.overrideIssuer, self.ui.overrideFeeAsset)
		mw.uiAccountAssetLink(self.ui.publishAccount, self.ui.publishFeeAsset)
		mw.uiAccountAssetLink(self.ui.settleAccount, self.ui.settleFeeAsset)
		for account_name in self.accounts:
			self.ui.accountBox.addItem(account_name)
			self.ui.transferFromAccount.addItem(account_name)
			self.ui.untransferFromAccount.addItem(account_name)
			self.ui.fundAccount.addItem(account_name)
			self.ui.unfundAccount.addItem(account_name)
			self.ui.claimAccount.addItem(account_name)
			self.ui.publishAccount.addItem(account_name)
			self.ui.settleAccount.addItem(account_name)
		for contact_name in self.contacts:
			self.ui.transferToAccount.addItem(contact_name)
			self.ui.overrideFromAccount.addItem(contact_name)
			self.ui.overrideToAccount.addItem(contact_name)
			self.ui.feedProducer.addItem(contact_name)
		set_combo(self.ui.transferToAccount, "")
		set_combo(self.ui.overrideToAccount, "")
		set_combo(self.ui.overrideFromAccount, "")
		set_combo(self.ui.feedProducer, "")
		
		self.feedupdater = RemoteFetch(manager=mw.Requests)
		
		if not(mw.is_advancedmode()):
			hide = [ self.ui.feeAsset, self.ui.feeAssetLabel,
			self.ui.transferFeeAsset, self.ui.transferFeeLabel,
			self.ui.untransferFeeAsset, self.ui.untransferFeeLabel,
			self.ui.fundFeeAsset, self.ui.fundFeeLabel,
			self.ui.unfundFeeAsset, self.ui.unfundFeeLabel,
			self.ui.claimFeeAsset, self.ui.claimFeeLabel,
			self.ui.overrideFeeAsset, self.ui.overrideFeeLabel,
			self.ui.publishFeeAsset, self.ui.publishFeeLabel ]
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
		
		stretch_table(self.ui.feeds, 5)
		self.ui.feeds.cellDoubleClicked.connect(self.feed_superclick)
		
		self.ui.isBitasset.stateChanged.connect(self.bitasset_toggle)
		
		self.ui.buttonBox.clicked.connect(self.route_buttonbox)
		
		self.ui.widgetFeedproducers.setVisible(False)
		
		self.ui.feedProducerAdd.clicked.connect(self.add_feed_producer)
		self.ui.feedProducer.lineEdit().returnPressed.connect(self.add_feed_producer)
		
		self.setupMode(self.mode)
		
		self.ui.totalEdit.setMaximum(GRAPHENE_MAX_SHARE_SUPPLY)
		self.ui.MCR.setMinimum(GRAPHENE_MIN_COLLATERAL_RATIO/10)
		self.ui.MCR.setMaximum(GRAPHENE_MAX_COLLATERAL_RATIO/10)
		self.ui.maxShortSqueeze.setMinimum(GRAPHENE_MIN_COLLATERAL_RATIO/10)
		self.ui.maxShortSqueeze.setMaximum(GRAPHENE_MAX_COLLATERAL_RATIO/10)
		
		if self.activeAccount:
			set_combo(self.ui.accountBox, self.activeAccount["name"])
		
		if self.asset:
			self.setupAsset(self.asset)
		else:
			self.bitasset_toggle(0)
			self.ui.precisionEdit.valueChanged.connect(self.precision_adjust)
			self.ui.totalEdit.valueChanged.connect(self.total_adjust)
			self.ui.totalEdit.setValue(GRAPHENE_MAX_SHARE_SUPPLY)
		
	
	def bitasset_toggle(self, state):
		self.ui.frameBitasset.setEnabled(bool(state))
		self.ui.isPredictionMarket.setEnabled(bool(state))
	
	def keyPressEvent(self, evt):
		if(evt.key() == QtCore.Qt.Key_Enter or evt.key() == QtCore.Qt.Key_Return):
			if self.ui.feedProducer.hasFocus():
				return
		super(AssetWindow, self).keyPressEvent(evt)
	
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
			if self.mode == "override":
				self.make_override()
			if self.mode == "reserve":
				self.make_reserve()
			if self.mode == "fund":
				self.make_fund()
			if self.mode == "unfund":
				self.make_unfund()
			if self.mode == "claim":
				self.make_claim()
			if self.mode == "publish":
				self.publish_feed()
			if self.mode == "settle":
				self.global_settle()
		
		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Cancel):
			self.reject()
		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Close):
			self.reject()
	
	def setupAsset(self, asset):
		self.setWindowTitle("Asset " + asset["symbol"])
		
		self.ui.symbolEdit.setText(asset["symbol"])
		self.ui.precisionEdit.setValue(int(asset["precision"]))
		self.precision_adjust(False)
		self.ui.totalEdit.setValue(int(asset["options"]["max_supply"] / pow(10, asset["precision"])))
		
		self.ui.symbolEdit.setEnabled(False)
		self.ui.precisionEdit.setEnabled(False)
		self.ui.totalEdit.setEnabled(False)
		self.ui.permList.setEnabled(False)
		
		self.ui.descriptionPlain.setPlainText(str(asset["options"]["description"]))
		
		self.ui.marketFee.setValue(int(asset["options"]["market_fee_percent"])/100)
		cer = asset["options"]["core_exchange_rate"]
		asset["options"]["core_exchange_rate"]["base"]["amount"] = int(cer["base"]["amount"])
		asset["options"]["core_exchange_rate"]["quote"]["amount"] = int(cer["quote"]["amount"])
		print(asset["symbol"], cer)
		try:
			rate = (int(cer["base"]["amount"])/pow(10, 5)) / (int(cer["quote"]["amount"])/pow(10, asset["precision"]))
		except:
			rate = 0
		self.ui.coreExchangeRate.setMaximum(1000000000000) # ?
		self.ui.coreExchangeRate.setDecimals(5) # BTS 5 - TODO: unhardcode?
		self.ui.coreExchangeRate.setValue(float(rate))
		
		perm_dict = todict(asset["options"]["issuer_permissions"])
		flag_dict = todict(asset["options"]["flags"])
		for i in range(0, self.ui.permList.count()):
			item = self.ui.permList.item(i)
			name = item.data(33)
			v = perm_dict.get(name, False)
			item.setCheckState(QtCore.Qt.Checked if v else QtCore.Qt.Unchecked)
		for i in range(0, self.ui.flagList.count()):
			item = self.ui.flagList.item(i)
			name = item.data(33)
			v = flag_dict.get(name, False)
			item.setCheckState(QtCore.Qt.Checked if v else QtCore.Qt.Unchecked)
		
		issuer = asset["issuer"]
		if not self.iso.offline:
			asset.refresh()
			try:
				issuer = self.iso.getAccount(issuer)
				issuer = issuer["name"]
			except:
				pass
		
		# Issue
		set_combo(self.ui.transferAsset, asset["symbol"])
		self.ui.transferAmount.setDecimals(asset["precision"])
		self.ui.transferAmount.setMaximum(
		int(asset["options"]["max_supply"]) / pow(10, asset["precision"]))
		set_combo(self.ui.transferFromAccount, issuer)
#		self.ui.transferFromAccount.setEnabled(False)
		
		# Override
		set_combo(self.ui.overrideAsset, asset["symbol"])
		self.ui.overrideAmount.setDecimals(asset["precision"])
		self.ui.overrideAmount.setMaximum(
		int(asset["options"]["max_supply"]) / pow(10, asset["precision"]))
		set_combo(self.ui.overrideIssuer, issuer, force=True)
		
		# Reserve
		set_combo(self.ui.untransferAsset, asset["symbol"])
		self.ui.untransferAmount.setDecimals(asset["precision"])
		self.ui.untransferAmount.setMaximum(
		int(asset["options"]["max_supply"]) / pow(10, asset["precision"]))
		if self.activeAccount:
			set_combo(self.ui.untransferFromAccount, self.activeAccount["name"])
		
		# Fund (fee pool)
		set_combo(self.ui.fundAsset, "BTS")
		self.ui.fundAmount.setDecimals(5)
		if self.activeAccount:
			set_combo(self.ui.fundAccount, self.activeAccount["name"])
		
		# Unfund (claim from fee pool)
		set_combo(self.ui.unfundAsset, "BTS")
		self.ui.unfundAmount.setDecimals(5)
		set_combo(self.ui.unfundAccount, issuer)
		v = self.iso.QAmount("BTS", int(asset['dynamic_asset_data']["fee_pool"]), 5)
		self.ui.unfundPool.setText(str(v).split(" ")[0])
		
		# Claim
		set_combo(self.ui.claimAsset, asset["symbol"])
		self.ui.claimAmount.setDecimals(asset["precision"])
		set_combo(self.ui.claimAccount, issuer)
		v = self.iso.QAmount(asset["symbol"], int(asset['dynamic_asset_data']["accumulated_fees"]), asset['precision'])
		self.ui.claimAccumulated.setText(str(v).split(" ")[0])
		
		# Edit
		set_combo(self.ui.accountBox, issuer)
		#self.ui.accountBox.setEnabled(False) # allow new_issuer
		self.ui.widgetFeedproducers.setVisible(True)
		
		# Feeds
		if asset.is_bitasset and self.mode in [ "publish", "edit", "bitasset" ]:
			table = self.ui.feeds
			j = -1
			for account_id, feed in asset["bitasset_data"]["feeds"]:
				date, feed = feed
				j += 1
				table.insertRow(j)
				try:
					sp = Price(feed["settlement_price"], blockchain_instance=self.iso.bts)
				except:
					sp = ""
				try:
					cer = Price(feed["core_exchange_rate"], blockchain_instance=self.iso.bts)
				except:
					cer = ""
				mcr = feed["maintenance_collateral_ratio"] / 100
				mssr = feed["maximum_short_squeeze_ratio"] / 100
				#name = self.iso.softAccountName(account_id)
				set_col(table, j, 0, account_id, data=account_id)
				set_col(table, j, 1, str(sp))
				set_col(table, j, 2, ("%.01f" % mcr) + " %")
				set_col(table, j, 3, ("%.01f" % mssr) + " %")
				set_col(table, j, 4, str(cer))
				set_col(table, j, 5, str(date).replace("T", " "))
			self.resync_feeds()
		else:
			self.hideTabs([TID_FEEDS])
		
		# Publish feed
		self.ui.settlementPrice.setDecimals(asset["precision"])
		self.ui.settlementPriceLabel.setText(asset["symbol"])
		self.ui.feedExchangeRate.setDecimals(asset["precision"])
		self.ui.feedExchangeRateLabel.setText(asset["symbol"])
		if self.activeAccount:
			set_combo(self.ui.publishAccount, self.activeAccount["name"])
		
		# Global settle
		self.ui.settlePrice.setDecimals(5)
		set_combo(self.ui.settleAccount, issuer)
#		if self.activeAccount:
#			set_combo(self.ui.settleAccount, self.activeAccount["name"])
		
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
			if self.mode in [ "publish", "edit", "bitasset" ]:
				for account_id, feed in bitasset["feeds"]:
					item = QtGui.QListWidgetItem(account_id)#self.iso.softAccountName(account_id))
					item.setData(99, account_id)
					item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
					item.setCheckState(QtCore.Qt.Checked)
					self.ui.feedProducers.addItem(item)
		else:
			self.ui.isBitasset.setCheckState(0)
			self.ui.isPredictionMarket.setVisible(False)
			self.ui.frameBitasset.setVisible(False)
	
	def setupMode(self, mode):
		if mode == "create":
			self.hideTabs(SECONDARY_TABS)
			self.hideTabs([TID_FEEDS])
			self.showTab(TID_MAIN)
		if mode == "edit":
			self.hideTabs(SECONDARY_TABS)
			self.showTab(TID_MAIN)
		if mode == "bitasset":
			self.hideTabs(SECONDARY_TABS)
			self.showTab(TID_BITASSET)
		if mode == "issue":
			self.hideTabsX([TID_ISSUE])
		if mode == "override":
			self.hideTabsX([TID_OVERRIDE])
		if mode == "reserve":
			self.hideTabsX([TID_RESERVE])
		if mode == "fund":
			self.hideTabsX([TID_FUND])
		if mode == "unfund":
			self.hideTabsX([TID_UNFUND])
		if mode == "claim":
			self.hideTabsX([TID_CLAIM])
		if mode == "publish":
			self.hideTabsX([TID_PUBLISH, TID_FEEDS])
			self.showTab(1)
		if mode == "settle":
			self.hideTabsX([TID_SETTLE])
	
	
	def showTab(self, i):
		self.ui.tabWidget.setCurrentIndex(i)
	
	def hideTabs(self, inds):
		for i in reversed(sorted(inds)):
			self.ui.tabWidget.removeTab(i)
	
	def hideTabsX(self, xindies):
		inds = list(range(0, self.ui.tabWidget.count()))
		for xindex in xindies:
			inds.pop(xindex)
		self.hideTabs(inds)

	def add_feed_producer(self):
		account_id = self.ui.feedProducer.currentText().strip()
		if not account_id:
			self.ui.feedProducer.setFocus()
			return False
		try:
			account = self.iso.getAccount(account_id)
		except Exception as e:
			showexc(e)
			return False
		
		item = QtGui.QListWidgetItem(account_id)
		item.setData(99, account["id"])
		item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
		item.setCheckState(QtCore.Qt.Checked)
		self.ui.feedProducers.addItem(item)
		
		set_combo(self.ui.feedProducer, "")
		return False

	def total_adjust(self, full=True):
		total = int(self.ui.totalEdit.value())
		req_precision = 16 - len(str(total))
		precision = int(self.ui.precisionEdit.value())
		print("Req precision:", req_precision, "current:", precision)
		if full and req_precision < precision:
			self.ui.precisionEdit.blockSignals(True)
			self.ui.precisionEdit.setValue(req_precision)
			self.precision_adjust(full=False)
			self.ui.precisionEdit.blockSignals(False)

	def precision_adjust(self, full=True):
		precision = int(self.ui.precisionEdit.value())
		if not precision: unit = "1"
		else: unit = "0." + ("0" * (precision-1)) + "1"
		self.ui.atomicUnit.setText(unit)
		req_total = int(GRAPHENE_MAX_SHARE_SUPPLY / pow(10, precision))
		total = int(self.ui.totalEdit.value())
		if full and req_total < total:
			self.ui.totalEdit.blockSignals(True)
			self.ui.totalEdit.setValue(req_total)
			self.ui.totalEdit.blockSignals(False)
	
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
		cer = self.asset["options"]["core_exchange_rate"]
		self.asset["options"]["core_exchange_rate"]["base"]["amount"] = int(cer["base"]["amount"])
		self.asset["options"]["core_exchange_rate"]["quote"]["amount"] = int(cer["quote"]["amount"])
		#from pprint import pprint
		#pprint(dict(self.asset))
		return {
		"symbol": self.asset["symbol"],
		"issuer": self.asset["issuer"],
		
		"precision": self.asset["precision"],
		"max_supply": int(self.asset["options"]["max_supply"]),
		"core_exchange_rate": self.asset["options"]["core_exchange_rate"],
		
		"new_issuer": self.asset["issuer"],
		"permissions": todict(self.asset["options"]["issuer_permissions"]),
		"flags": todict(self.asset["options"]["flags"]),
		"description": self.asset["options"]["description"],
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
	def prev_feed_producers(self):
		r = [ ]
		for account_id, feed in self.asset["bitasset_data"]["feeds"]:
			r.append(account_id)
		return r
	
	def collect_cer(self, elem, precision, inv=False):
		rate = float(elem.value())
		cer = { "base": { "amount": 0, "asset_id": "1.3.0" },
			"quote": { "amount": 0, "asset_id": "1.3.1" } }
		#if rate < 1:
		#	cer["quote"]["amount"] = 1 * pow(10, precision)
		#	cer["base"]["amount"] = 1/rate * pow(10, 5)
		#else:
		cer["quote"]["amount"] = 1 * pow(10, precision)
		cer["base"]["amount"] = rate * pow(10, 5)
		if self.asset:
			cer["quote"]["asset_id"] = self.asset["id"]
		if inv:
			tmp = dict(cer["quote"])
			cer["quote"] = dict(cer["base"])
			cer["base"] = tmp
		return cer

	def collect_options(self):
		issuer = self.ui.accountBox.currentText()
		try:
			issuer = self.iso.getAccount(issuer)
			issuer = issuer["id"]
		except:
			pass
		symbol = self.ui.symbolEdit.text()
		if not len(symbol):
			raise Exception("Enter asset symbol")
		whole_coins = int(self.ui.totalEdit.value())
		precision = int(self.ui.precisionEdit.value())
		cer = self.collect_cer(self.ui.coreExchangeRate, precision)
		return {
		"symbol": symbol,
		"issuer": issuer,
		
		"precision": precision,
		"max_supply": int(whole_coins * pow(10, precision)),
		"core_exchange_rate": cer,
		
		"new_issuer": issuer,
		"permissions": self.collect_flags(self.ui.permList),
		"flags": self.collect_flags(self.ui.flagList),
		"description": self.ui.descriptionPlain.toPlainText(),
		"is_prediction_market": bool(self.ui.isPredictionMarket.checkState()),
		"market_fee_percent": self.ui.marketFee.value()*100,
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
	
	def collect_feed_producers(self):
		elem = self.ui.feedProducers
		r = [ ]
		n = elem.count()
		for i in range(0, n):
			item = elem.item(i)
			account_id = item.data(99)
			if item.checkState():
				r.append(account_id)
		return r
	
	def resync_feeds(self, ids=None):
		table = self.ui.feeds
		if ids is None:
			ids = [ ]
			n = table.rowCount()
			for i in range(0, n):
				ids.append( table_coldata(table, i, 0) )
		self.feedupdater.fetch(
			self.resync_feeds_bg, ids,
			ready_callback=self.resync_feeds_ui,
			error_callback=self.resync_feeds_abort,
			ping_callback=self.resync_feeds_ping,
			description="Updating feeds")
	
	def resync_feeds_bg(self, ids):
		objs = self.iso.bts.rpc.get_objects(ids)
		account_names = { }
		for obj in objs:
			account_names[obj["id"]] = obj["name"]
		return account_names
	
	def resync_feeds_ui(self, uid, args):
		account_names = args
		table = self.ui.feeds
		n = table.rowCount()
		for j in range(0, n):
			account_id = table_coldata(table, j, 0)
			if account_id in account_names:
				set_col(table, j, 0, account_names[account_id], data=account_id)
		table = self.ui.feedProducers
		n = table.count()
		for j in range(0, n):
			account_id = table.item(j).data(99)
			if account_id in account_names:
				table.item(j).setText(account_names[account_id])
	
	def resync_feeds_abort(self, uid, error):
		pass
	def resync_feeds_ping(self, uid, pt, pd):
		pass
	
	def feed_superclick(self, row, column):
		table = self.ui.feeds
		val = table.item(row, column).text()
		if column == 2: #MCR
			v = float(val.split(" ")[0])
			self.ui.MCR.setValue(v)
		elif column == 3: #MSSR
			v = float(val.split(" ")[0])
			self.ui.maxShortSqueeze.setValue(v)
		else:
			qclip(val)
	
	def attempt_create(self):
		fee_asset = anyvalvis(self.ui.feeAsset, None)
		try:
			options = self.collect_options()
		except Exception as e:
			showexc(e)
			return False
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
			return True
		return False
	
	def attempt_update(self):
		fee_asset = anyvalvis(self.ui.feeAsset, None)#.currentText()
		new_issuer = None
		
		vs = [ ]
		
		prev_options = self.prev_options()
		options = self.collect_options()
		if options["issuer"] != prev_options["issuer"]:
			new_issuer = options["issuer"]
			options["issuer"] = prev_options["issuer"]
			options["new_issuer"] = prev_options["new_issuer"]
		if not(dict_same(prev_options, options)):
			options.pop("permissions")
			options.pop("precision")
			options.pop("max_supply")
			options.pop("new_issuer")
			v1 = QTransactionBuilder.VUpdateAsset(
				fee_asset=fee_asset,
				isolator=self.iso,
				**options
			)
			vs.append( v1 )
		
		bitoptions = self.collect_bitoptions()
		if bitoptions:
			prev_bitoptions = self.prev_bitoptions()
			if not(dict_same(prev_bitoptions, bitoptions)):
				v2 = QTransactionBuilder.VUpdateBitAsset(
					fee_asset=fee_asset,
					isolator=self.iso,
					**bitoptions
				)
				vs.append( v2 )
			prev_feedproducers = self.prev_feed_producers()
			feed_producers = self.collect_feed_producers()
			if not(set_same(prev_feedproducers, feed_producers)):
				v3 = QTransactionBuilder.VUpdateFeedProducers(
					options["symbol"],
					options["issuer"],
					feed_producers,
					fee_asset=fee_asset,
					isolator=self.iso
				)
				vs.append( v3 )
		
		if new_issuer:
			v4 = QTransactionBuilder.VUpdateAssetIssuer(
				options["symbol"],
				prev_options["issuer"],
				new_issuer,
				fee_asset=fee_asset,
				isolator=self.iso
			)
			vs.append( v4 )

		if len(vs) < 1:
			showmsg("No change")
			self.reject()
			return False
		
		r = QTransactionBuilder._QExecS(self.iso, vs)
		if r:
			self.accept()
			return True
		return False
	
	def make_transfer(self):
		account_from = self.ui.transferFromAccount.currentText()
		account_to = self.ui.transferToAccount.currentText()
		asset_name = self.ui.transferAsset.currentText()
		asset_amount = self.ui.transferAmount.text()
		memo_text = self.ui.transferMemo.toPlainText()
		fee_asset = anyvalvis(self.ui.transferFeeAsset, None)
		
		try:
			trx = QTransactionBuilder.QIssueAsset(
				asset_name,
				asset_amount,
				account_from,
				account_to,
				memo=memo_text,
				fee_asset=fee_asset,
				isolator=self.iso)
			if trx:
				self.accept()
				return True
		except Exception as error:
			showexc(error)
		return False
	
	def make_override(self):
		account_issuer = self.ui.overrideIssuer.currentText()
		account_from = self.ui.overrideFromAccount.currentText()
		account_to = self.ui.overrideToAccount.currentText()
		asset_name = self.ui.overrideAsset.currentText()
		asset_amount = self.ui.overrideAmount.text()
		memo_text = self.ui.overrideMemo.toPlainText()
		fee_asset = anyvalvis(self.ui.overrideFeeAsset, None)
		
		try:
			trx = QTransactionBuilder.QOverrideTransfer(
				asset_name,
				asset_amount,
				account_issuer,
				account_from,
				account_to,
				memo=memo_text,
				fee_asset=fee_asset,
				isolator=self.iso)
			if trx:
				self.accept()
				return True
		except Exception as error:
			showexc(error)
		return False

	def make_reserve(self):
		account_from = self.ui.untransferFromAccount.currentText()
		asset_name = self.ui.untransferAsset.currentText()
		asset_amount = self.ui.untransferAmount.text()
		fee_asset = anyvalvis(self.ui.untransferFeeAsset, None)
		
		try:
			trx = QTransactionBuilder.QReserveAsset(
				asset_name,
				asset_amount,
				account_from,
				fee_asset=fee_asset,
				isolator=self.iso)
			if trx:
				self.accept()
				return True
		except Exception as error:
			showexc(error)
		return False
	
	def make_fund(self):
		account_from = self.ui.fundAccount.currentText()
		asset_name = self.asset["symbol"]
		bts_amount = self.ui.fundAmount.value()
		fee_asset = anyvalvis(self.ui.fundFeeAsset, None)
		
		try:
			trx = QTransactionBuilder.QFundFeePool(
				asset_name,
				bts_amount,
				account_from,
				fee_asset=fee_asset,
				isolator=self.iso)
			if trx:
				self.accept()
				return True
		except Exception as error:
			showexc(error)
		return False
	
	def make_unfund(self):
		account_from = self.ui.unfundAccount.currentText()
		asset_name = self.asset["symbol"]
		asset_amount = self.ui.unfundAmount.text()
		fee_asset = anyvalvis(self.ui.unfundFeeAsset, None)
		
		try:
			trx = QTransactionBuilder.QClaimFeePool(
				asset_name,
				asset_amount,
				account_from,
				fee_asset=fee_asset,
				isolator=self.iso)
			if trx:
				self.accept()
				return True
		except Exception as error:
			showexc(error)
		return False

	def make_claim(self):
		account_from = self.ui.claimAccount.currentText()
		asset_name = self.ui.claimAsset.currentText()
		asset_amount = self.ui.claimAmount.text()
		fee_asset = anyvalvis(self.ui.claimFeeAsset, None)
		
		try:
			trx = QTransactionBuilder.QClaimMarketFees(
				asset_name,
				asset_amount,
				account_from,
				fee_asset=fee_asset,
				isolator=self.iso)
			if trx:
				self.accept()
				return True
		except Exception as error:
			showexc(error)
		return False

	def publish_feed(self):
		precision = self.asset["precision"]
		stp = self.collect_cer(self.ui.settlementPrice, precision, True)
		cer = self.collect_cer(self.ui.feedExchangeRate, precision, True)
		account_from = self.ui.publishAccount.currentText()
		asset_name = self.asset["symbol"]
		mcr = self.ui.MCR.value() * 10
		mssr = self.ui.maxShortSqueeze.value() * 10
		fee_asset = anyvalvis(self.ui.publishFeeAsset, None)
		
		try:
			trx = QTransactionBuilder.QPublishFeed(
				asset_name,
				account_from,
				stp, mcr, mssr, cer,
				fee_asset=fee_asset,
				isolator=self.iso)
			if trx:
				self.accept()
				return True
		except Exception as error:
			showexc(error)
		return False

	def global_settle(self):
		precision = self.asset["precision"]
		stp = self.collect_cer(self.ui.settlePrice, precision)
		account_from = self.ui.settleAccount.currentText()
		asset_name = self.asset["symbol"]
		fee_asset = anyvalvis(self.ui.settleFeeAsset, None)
		
		try:
			trx = QTransactionBuilder.QGlobalSettle(
				asset_name,
				account_from,
				stp,
				fee_asset=fee_asset,
				isolator=self.iso)
			if trx:
				self.accept()
				return True
		except Exception as error:
			showexc(error)
		return False
