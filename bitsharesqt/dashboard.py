# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QTableWidgetItem

from bitshares.amount import Amount
from .transactionbuilder import QTransactionBuilder
from .voting import VotingWindow
from .createasset import AssetWindow

from .netloc import RemoteFetch
from .utils import *

import json
from pprint import pprint

from uidef.dashboard import Ui_DashboardTab
_translate = QtCore.QCoreApplication.translate


import logging
log = logging.getLogger(__name__)

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s


class DashboardTab(QtWidgets.QWidget):
	
	def __init__(self, *args, **kwargs):
		self.ping_callback = kwargs.pop("ping_callback", None)
		simplify = kwargs.pop("simplify", False)
		super(DashboardTab, self).__init__(*args, **kwargs)
		self.ui = Ui_DashboardTab()
		self.ui.setupUi(self)
		
		stretch_table(self.ui.balanceTable)
		
		self.updater = RemoteFetch()
		
		self.ui.transferGroup.setVisible(False)
		
		if simplify:
			self.ui.upgradeButton.setVisible(False)
			self.ui.voteButton.setVisible(False)
			self.ui.upgradeFeeAsset.setVisible(False)
			self.ui.upgradeFeeLabel.setVisible(False)
			return
		
		qmenu(self.ui.balanceTable, self.show_balances_submenu)
		self.ui.upgradeButton.clicked.connect(self.make_upgrade)
		self.ui.transferButton.clicked.connect(self.make_transfer)
		
		self.ui.balanceTable.itemClicked.connect(self.balance_click)
		self.ui.balanceTable.itemDoubleClicked.connect(self.balance_dblclick)
		
		self._index = 0
		self._asset_name = None
		
		self.ui.voteButton.clicked.connect(self.show_voting)
	
	def balance_click(self):
		j = table_selrow(self.ui.balanceTable)
		if j <= -1:
			return
		symbol = self.ui.balanceTable.item(j, 1).text()
		self.quick_transfer(symbol)
	
	def quick_transfer(self, symbol, to=None, memo=None):
		try:
			asset = self.iso.getAsset(symbol, force_remote=False)
		except Exception as error:
			showexc(error)
			return
		
		if self._asset_name != symbol:
			self.ui.transferAmount.setValue(0)
		self._asset = asset
		self._asset_name = symbol
		self.ui.transferAmount.setDecimals(asset["precision"])
		self.ui.transferAmount.setMaximum(
		asset["options"]["max_supply"] / pow(10, asset["precision"]))
		self.ui.transferGroup.setTitle("Transfer " + symbol)
		self.ui.transferGroup.setVisible(True)
		
		if to:
			if not(isinstance(to, str)):
				to = to["name"]
			set_combo(self.ui.transferToAccount, to)
		
		#if amount:
		#	pass
		
		if not(memo is None):
			self.ui.transferMemo.setPlainText(memo)
	
	def balance_dblclick(self, item):
		if item.column() != 0:
			return
		t = item.text().replace(",","")
		self.ui.transferAmount.setValue(float(t))
	
	def show_balances_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Quick Transfer", self.balance_click)
		qaction(self, menu, "Copy Balance", self._dash_copy_balance)
		#qaction(self, menu, "Transfer...", self._dash_transfer)
		qaction(self, menu, "Buy...", self._dash_buy_asset)
		qaction(self, menu, "Sell...", self._dash_sell_asset)
		qaction(self, menu, "Open Market", self._dash_openmarket_asset)
		qaction(self, menu, "Blind...", self._dash_blind_asset)
		qaction(self, menu, "Burn...", self._dash_burn_asset)
		menu.addSeparator()
		qaction(self, menu, "Details", self._asset_details)
		qmenu_exec(self.ui.balanceTable, menu, position)
	
	def _dash_transfer(self):
		j = table_selrow(self.ui.balanceTable)
		if j <= -1:
			return
		amount = float( self.ui.balanceTable.item(j, 0).text() )
		symbol = self.ui.balanceTable.item(j, 1).text()
		try:
			asset = self.iso.getAsset(symbol, force_remote=False)
		except Exception as error:
			showexc(error)
		app().mainwin.OTransfer(
			from_=self._account["name"],
			asset=asset["symbol"]
		)
	
	def _dash_copy_balance(self):
		j = table_selrow(self.ui.balanceTable)
		if j <= -1:
			return
		amount = self.ui.balanceTable.item(j, 0).text()
		qclip(amount)
	
	def _dash_buy_asset(self):
		j = table_selrow(self.ui.balanceTable)
		if j <= -1:
			return
		symbol = self.ui.balanceTable.item(j, 1).text()
		app().mainwin.FSell(
			account    = self._account["name"],
			buy_asset  = symbol,
		)
	
	def _dash_sell_asset(self):
		j = table_selrow(self.ui.balanceTable)
		if j <= -1:
			return
		amount = float( self.ui.balanceTable.item(j, 0).text() )
		symbol = self.ui.balanceTable.item(j, 1).text()
		app().mainwin.FSell(
			account     = self._account["name"],
			sell_asset  = symbol,
			sell_amount = amount,
		)
	
	def _dash_openmarket_asset(self):
		j = table_selrow(self.ui.balanceTable)
		if j <= -1:
			return
		symbol = self.ui.balanceTable.item(j, 1).text()
		asset = self.iso.getAsset(symbol)
		desc = asset["options"]["description"]
		market = None
		try:
			market = json.loads(desc)["market"]
		except:
			pass
		if not(market):
			market = "BTS"
		try:
			app().mainwin.openMarket(symbol, market)
		except Exception as err:
			showexc(err)
	
	def _dash_blind_asset(self):
		j = table_selrow(self.ui.balanceTable)
		if j <= -1:
			return
		amount = float( self.ui.balanceTable.item(j, 0).text() )
		symbol = self.ui.balanceTable.item(j, 1).text()
		app().mainwin.OBlind(
			account     = self._account["name"],
			asset  = symbol,
			amount = amount,
		)
	
	def _dash_burn_asset(self):
		j = table_selrow(self.ui.balanceTable)
		if j <= -1:
			return
		amount = float( self.ui.balanceTable.item(j, 0).text() )
		symbol = self.ui.balanceTable.item(j, 1).text()
		#app().mainwin.OBlind(
		#	account     = self._account["name"],
		#	asset  = symbol,
		#	amount = amount,
		#)
		asset_name = symbol
		if not asset_name:
			return
		asset = self.iso.getAsset(asset_name)

		win = AssetWindow(isolator=self.iso, mode="reserve",
			asset=asset,
			accounts=app().mainwin.account_names,
			account=app().mainwin.activeAccount)
		win.exec_()
	
	def _asset_details(self):
		j = table_selrow(self.ui.balanceTable)
		if j <= -1:
			return
		symbol = self.ui.balanceTable.item(j, 1).text()
		
		app().mainwin.ui.marketFilter.setText(symbol)
		try:
			app().mainwin.ui.marketFilter.textEdited.emit(symbol)
			app().mainwin.display_asset(symbol, force_remote=False)
		except Exception as error:
			showexc(error)
		app().mainwin.tagToFront("^markets")
	
	def make_upgrade(self):
		account_name = self._account['name']
		fee_asset = self.ui.upgradeFeeAsset.currentText()
		try:
			trx = QTransactionBuilder.QUpgradeAccount(
				account_name,
				fee_asset=fee_asset,
				isolator=self._iso)
		except BaseException as error:
			showexc(error)
	
	def make_transfer(self):
		account_from = self._account['name']
		account_to = self.ui.transferToAccount.currentText()
		asset_name = self._asset_name
		asset_amount = self.ui.transferAmount.text()
		memo_text = self.ui.transferMemo.toPlainText()
		fee_asset = anyvalvis(self.ui.transferFeeAsset, None)#.currentText()
		buffer = app().mainwin.buffering()
		
		if not account_to:
			self.ui.transferToAccount.setFocus()
			return False
		
		
		try:
			v = QTransactionBuilder.VTransfer(
				asset_name,
				asset_amount,
				account_from,
				account_to,
				memo=memo_text,
				fee_asset=fee_asset,
				isolator=self.iso)
			if buffer:
				app().mainwin._txAppend(*v)
			else:
				QTransactionBuilder._QExec(self.iso, v)
		except BaseException as error:
			showexc(error)
			return False
		return True

	def show_voting(self):
		if not(self.iso.is_connected()):
			showmsg("Must be online to vote")
			return False
		try:
			w = VotingWindow(
				accounts=app().mainwin.account_names,
				account=self._account,
				isolator=self.iso
			)
			r = w.exec_()
			w.close()
		except Exception as error:
			showexc(error)
			return False

	def openAccount(self, iso, account):
		self._iso = self.iso = iso
		self._account = account
		
		# local
		self.refresh_dashboard(account["name"], remote=False)
		balances = self.iso.getBalances(account["id"], force_local=True)
		self.refresh_balances(balances)
		
		#self.ui.dashAccountId.setText( account['id'] )
		#self.ui.dashAccountName.setText( account['name'] )
		# remote
		self.resync()

	def resync(self):
		self.updater.fetch(
			self.mergeAccount_before, self._iso, self._account,
			ready_callback=self.mergeAccount_after,
			error_callback=self.mergeAccount_abort,
			ping_callback=self.ping_callback,
			description="Updating balances")

	def mergeAccount_before(self, iso, account):
		
		self.iso = iso
		
		#iso._wait_online(timeout=3) # will raise exception
		#if not(iso.is_connected()):
		#	raise Exception
		
		# related names
		softname = iso.softAccountName
		softname(account['registrar'])
		softname(account['referrer'])
		softname(account['options']['voting_account'])
		
		# balances
		balances = self.iso.getBalances(account["id"], force_remote=True)
		
		return (balances, account.name, )

	def mergeAccount_after(self, request_id, args):
		(balances, account_name, ) = args
		
		# refresh info
		self.refresh_dashboard(account_name, remote=False)
		
		# balances
		self.refresh_balances(balances)

	def mergeAccount_abort(self, request_id, error):
		log.error("Failed to re-sync account: %s", str(error))

	def ping_callback(self):
		pass

	def refresh_dashboard(self, account_name, remote=True):
		
		softname = lambda x: self.iso.softAccountName(x, remote)
		account = self._account #self.iso.getAccount(account_name)
		if remote:
			account = self.iso.getAccount(account_name, force_remote=True, cache=True)
		
		self.ui.dashAccountId.setText( account['id'] )
		self.ui.dashAccountName.setText( account['name'] )
		self.ui.dashRegistrar.setText( softname(account['registrar']) )
		self.ui.dashReferrer.setText( softname(account['referrer']) )
		self.ui.dashVotesAs.setText( softname(account['options']['voting_account']) )
		
		up = not(account.is_ltm)
		self.ui.upgradeButton.setEnabled(up)
		self.ui.upgradeFeeLabel.setEnabled(up)
		self.ui.upgradeFeeAsset.setEnabled(up)
		
	def refresh_balances(self, balances):
		
		if (len(balances) == 0): # fake balance
			o = lambda: None
			o.symbol = "BTS"
			o.amount = "0.00000"
			balances = [ o ]
		
		table = self.ui.balanceTable
		table.setRowCount(0)
		table.setRowCount(len(balances))
		#if self.single_user_mode:
		#	self.clear_asset_names()
		fc = self.ui.transferFeeAsset
		fc.clear()
		
		uc = self.ui.upgradeFeeAsset
		uc.clear()
		
		j = -1
		icon = qicon(":/icons/images/token.png")
		for o in balances:
			j += 1
			
			try:
				namt = self.iso.softAmountStr(o.amount, o.symbol)
			except:
				namt = str(o.amount)
			table.setItem(j, 0, QtGui.QTableWidgetItem(namt))
			table.item(j, 0).setIcon( icon )
			table.setItem(j, 1, QtGui.QTableWidgetItem(str(o.symbol)))
			
			fc.addItem(o.symbol)
			uc.addItem(o.symbol)
			#if self.single_user_mode:
			#	self.add_asset_name(o.symbol)
		
		table.sortByColumn(1, QtCore.Qt.AscendingOrder)