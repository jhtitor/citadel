# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.exchange import Ui_ExchangeTab
_translate = QtCore.QCoreApplication.translate

from PyQt5.QtWidgets import QTableWidgetItem

from .transactionbuilder import QTransactionBuilder

from .netloc import RemoteFetch
from .utils import *
import json

import logging
log = logging.getLogger(__name__)

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class OrderTab(QtWidgets.QWidget):
	
	def __init__(self, *args, **kwargs):
		self.ping_callback = kwargs.pop("ping_callback", None)
		super(OrderTab, self).__init__(*args, **kwargs)
		self.ui = Ui_ExchangeTab()
		self.ui.setupUi(self)
		
		self._index = 2
		
		self.updater = RemoteFetch()
		
		self.sell_estimater = RemoteFetch()
		
		stretch_table(self.ui.table)
		
		qmenu(self.ui.table, self.show_orders_submenu)
		
		mw = app().mainwin
		mw.uiExpireSliderLink(self.ui.sellexpireEdit, self.ui.sellexpireSlider)
		
		#self.ui.sellerBox.currentIndexChanged.connect(self.mini_reacc)
		#self.ui.transferFromAccount.currentIndexChanged.connect(self.mini_reacc)
		
		mw.uiAssetLink(self.ui.sellAmountSpin, self.ui.sellAssetCombo)
		mw.uiAssetLink(self.ui.buyAmountSpin, self.ui.buyAssetCombo)
		
		on_spin(self.ui.sellAmountSpin, self.sell_main_amount_changed)
		on_spin(self.ui.buyAmountSpin, self.sell_alt_amount_changed)
		# also, when asset type changes
		on_combo(self.ui.sellAssetCombo, self.sell_alt_amount_changed)
		on_combo(self.ui.buyAssetCombo, self.sell_main_amount_changed)
		
		mw.uiAssetsMarketLink(
			self.ui.sellAssetCombo,
			self.ui.buyAssetCombo,
			self.ui.bidPrice,
			self.ui.askPrice,
			self.ui.sellOpenMarketButton)
		
		self.ui.sellButton.clicked.connect(self.make_limit_order)
		
	def make_limit_order(self):
		#account_from = self.ui.sellerBox.currentText()
		account_from = self._account["name"] #ui.sellerBox.currentText()
		sell_asset_name = self.ui.sellAssetCombo.currentText()
		sell_asset_amount = self.ui.sellAmountSpin.value()
		buy_asset_name = self.ui.buyAssetCombo.currentText()
		buy_asset_amount = self.ui.buyAmountSpin.value()
		expire_seconds = deltasec(self.ui.sellexpireEdit.text())
		expire_fok = self.ui.fokCheckbox.isChecked()
		
		fee_asset = anyvalvis(self.ui.sellFeeAsset, None)#.currentText()
		buffer = app().mainwin.buffering()
		
		try:
			v = QTransactionBuilder.VSellAsset(
				account_from,
				sell_asset_name,
				sell_asset_amount,
				buy_asset_name,
				buy_asset_amount,
				expiration=expire_seconds,
				fill_or_kill=expire_fok,
				fee_asset=fee_asset,
				isolator=self._iso)
			if buffer:
				app().mainwin._txAppend(*v)
			else:
				QTransactionBuilder._QExec(self._iso, v)
		except BaseException as error:
			showexc(error)
			return False
		return True
	
	def refresh_balances(self, balances):
		if (len(balances) == 0): # fake balance
			o = lambda: None
			o.symbol = "BTS"
			o.amount = "0.00000"
			balances = [ o ]
		
		elems = [
			self.ui.sellAssetCombo,
			self.ui.buyAssetCombo,
			self.ui.sellFeeAsset,
		]
		for combo in elems:
			keys = [ o.symbol for o in balances ]
			sync_combo(combo, keys)
	
	def refreshUi_ping(self):
		pass
	
	def sell_main_amount_changed(self):
		sell_asset = self.ui.sellAssetCombo.currentText()
		buy_asset = self.ui.buyAssetCombo.currentText()
		sell_amount = self.ui.sellAmountSpin.value()
		
		if not(sell_asset) or not(buy_asset) or not(sell_amount):
			return
		
		self.sell_estimater.fetch(
			self.sell_estimate, sell_asset, sell_amount,
					buy_asset, None,
			ready_callback=self.sell_estimated,
			error_callback=self.sell_estimation_failed,
			ping_callback=self.refreshUi_ping,
		)
	
	def sell_alt_amount_changed(self):
		sell_asset = self.ui.sellAssetCombo.currentText()
		buy_asset = self.ui.buyAssetCombo.currentText()
		buy_amount = self.ui.buyAmountSpin.value()
		
		if not(sell_asset) or not(buy_asset) or not(buy_amount):
			return
		
		self.sell_estimater.fetch(
			self.sell_estimate, sell_asset, None,
					buy_asset, buy_amount,
			ready_callback=self.sell_estimated,
			error_callback=self.sell_estimation_failed,
			ping_callback=self.refreshUi_ping,
		)
	
	def sell_estimate(self, sell_asset, sell_amount, buy_asset, buy_amount):
		iso = self._iso
		asset_a = iso.getAsset(sell_asset)
		asset_b = iso.getAsset(buy_asset)
		
		mtype = sell_asset + ":" + buy_asset
		from bitshares.market import Market
		
		#market = Market(mtype, blockchain_instance=self._iso.bts)
		#tick = market.ticker()
		tick = iso.bts.rpc.get_ticker(asset_a["id"], asset_b["id"])
		
		highestBid = float(tick['highest_bid']) #        return self["price"]
		lowestAsk = float(tick['lowest_ask'])   #        return self["price"]
		
		if buy_amount:
			amt = float(buy_amount)
			re = amt * highestBid
			#self.ui.sellAmountSpin.setValue( re )
		
		if sell_amount:
			amt = float(sell_amount)
			re = amt / highestBid
			#self.ui.buyAmountSpin.setValue( re )
		
		#self.ui.sellComment.setText( str(tick) )
		
		return (re, buy_amount, sell_amount, tick)
	
	def sell_estimated(self, uid, args):
		(re, buy_amount, sell_amount, tick) = args
		
		if buy_amount:
			elem = self.ui.sellAmountSpin
		
		if sell_amount:
			elem = self.ui.buyAmountSpin
		
		elem.blockSignals(True)
		elem.setValue( re )
		elem.blockSignals(False)
		
		self.ui.bidPrice.setText("Bid: " + tick["highest_bid"])
		self.ui.askPrice.setText("Ask: " + tick["lowest_ask"])
		self.ui.bidPrice.hide()
		self.ui.askPrice.hide()

	def sell_estimation_failed(self, uid, error):
		pass


	def show_orders_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Cancel Order...", self.cancel_order)
		qaction(self, menu, "Open Market", self.open_market)
		menu.exec_(self.ui.table.viewport().mapToGlobal(position))
	
	def open_market(self):
		table = self.ui.table
		row = table_selrow(table)
		col_a = table.item(row, 1).text()
		col_b = table.item(row, 2).text()
		asset_name_a = str.split(col_a, " ")[1]
		asset_name_b = str.split(col_b, " ")[1]
		
		app().mainwin.openMarket(asset_name_a, asset_name_b)
	
	
	def cancel_order(self):
		table = self.ui.table
		row = table_selrow(table)
		if row <= -1:
			return False
		order_id = table.item(row, 0).text()
		#b = table.item(index, 1).text()
		buffer = app().mainwin.buffering()
		try:
			v = QTransactionBuilder.VCancelOrder(
				self._account_name,
				order_id,
				#fee_asset=fee_asset,
				isolator=self._iso)
			if buffer:
				app().mainwin._txAppend(*v)
			else:
				QTransactionBuilder._QExec(self._iso, v)
		except BaseException as error:
			showexc(error)
			return False
		return True
	
	
	def openOrders(self, iso, account):
		self._iso = iso
		self._account = account
		balances = iso.getBalances(account["id"], force_remote=False)
		self.refresh_balances(balances)
		self.resync()
	
	def resync(self):
		self.updater.fetch(
			self.mergeOrders_before, self._iso, self._account,
			ready_callback=self.mergeOrders_after,
			error_callback=self.mergeOrders_error,
			ping_callback=self.ping_callback,
			description="Refreshing orders")
	
	def mergeOrders(self, iso, account):
		self._iso = iso
		self.mergerOrders_after(0, self.mergeOrders_before(iso, account))
	
	def mergeOrders_before(self, iso, account):
		from bitshares.account import Account
		account.refresh()
		
		orders = [ order for order in account.openorders ]
		
		return (orders, account.name, )
	
	def mergeOrders_after(self, request_id, args):
		(added, account_name, ) = args
		
		self._account_name = account_name
		
		table = self.ui.table
		
		table.setRowCount(0)
		
		j = -1
		for order in added:
			j += 1
			
			table.insertRow(j)
			table.setItem(j, 0, QTableWidgetItem( str(order['id'] )))
			table.item(j, 0).setIcon(qicon(":/icons/images/limit_order.png"))
			set_col(table, j, 1, str(order["quote"]), color=COLOR_GREEN )
			set_col(table, j, 2, str(order["base"]), color=COLOR_RED )
			set_col(table, j, 3, str(order["price"]) )
	
	def mergeOrders_error(self, request_id, error):
		log.debug("Failed to merge orders: %s" % (str(error)))
