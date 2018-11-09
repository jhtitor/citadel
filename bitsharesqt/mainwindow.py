from PyQt5 import QtCore, QtGui
from uidef.mainwindow import Ui_MainWindow
_translate = QtCore.QCoreApplication.translate
import uidef.res_rc

from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtGui import QTextCursor

from .isolator import BitsharesIsolator
from bitsharesextra.storage import BitsharesStorageExtra, DataDir
from bitsharesbase.account import PrivateKey

from .version import VERSION, UNIX_NAME, library_versions
from .accountwizard import AccountWizard
from .walletwizard import WalletWizard, RecentWallets
from .memowindow import MemoWindow
from .createasset import AssetWindow
from .settings import SettingsWindow
from .dashboard import DashboardTab
from .history import HistoryTab
from .ordertab import OrderTab
from .market import MarketTab
from .transactionbuilder import QTransactionBuilder
from .contacts import WindowWithContacts
from .assets import WindowWithAssets
from .topmarkets import WindowWithMarkets
from .gateway import WindowWithGateway
from .blind import WindowWithBlind
from .tabwrangler import WindowWithTabWrangler
from .trxbuffer import WindowWithTrxBuffer

from .isolator import ResourceUnavailableOffline, WalletLocked

from .netloc import RemoteFetch
from .work import Request
from .utils import *
import logging
log = logging.getLogger(__name__)

class MainWindow(QtGui.QMainWindow,
	WindowWithContacts,
	WindowWithAssets,
	WindowWithMarkets,
	WindowWithGateway,
	WindowWithBlind,
	WindowWithTabWrangler,
	WindowWithTrxBuffer,
	):
	
	background_update = QtCore.pyqtSignal(int, str, object)
	
	log_record = QtCore.pyqtSignal(object)
	
	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('iso', None)
		super(MainWindow, self).__init__(*args, **kwargs)
		
		
		self.ui = ui = Ui_MainWindow()
		self.ui.setupUi(self)
		
		self.setupStatusBar()
		
		self.activeAccount = None
		self.refreshUi_title()
		
		self.prepareAdvancedMode()
		
		self.init_operations()
		
		self.account_boxes = [
			self.ui.accountsList,
			self.ui.statusAccounts,
			self.ui.gatewaySellAccount,
			self.ui.gatewayBuyAccount,
			self.ui.transferFromAccount,
			self.ui.sellerBox,
			#self.ui.marketAccountBox,
			self.ui.blindFromAccount,
		]
		self.contact_boxes = [
			self.ui.transferToAccount,
			self.ui.blindToAccount,
		]
		self.asset_boxes = [
			self.ui.transferAsset,
			self.ui.transferFeeAsset,
			self.ui.sellFeeAsset,
			self.ui.sellAssetCombo,
			self.ui.buyAssetCombo,
			self.ui.blindFromAsset,
			self.ui.blindFromFeeAsset,
		]
		
		ui.actionNew_wallet.triggered.connect(self.new_wallet_wizard)
		ui.actionOpen_wallet.triggered.connect(self.reopen_wallet)
		
		ui.actionClose_wallet.triggered.connect(self.close_wallet)
		ui.actionLock_wallet.triggered.connect(self.lock_wallet)
		ui.actionUnlock_wallet.triggered.connect(self.unlock_wallet)
		
		ui.actionConnect.triggered.connect(self.connect_to_node)
		ui.actionDisconnect.triggered.connect(self.disconnect_from_node)
		
		ui.actionQuit.triggered.connect(self.quit_program)
		
		ui.actionClose_wallet.setEnabled(False)
		
		ui.actionAdd_account.triggered.connect(self.add_account)
		ui.actionSign_Read_memo.triggered.connect(self.open_memowindow)
		ui.actionTransaction_builder.triggered.connect(self.open_transactionbuffer)
		
		ui.actionCreate_Asset.triggered.connect(self.open_createassetwindow)
		
		ui.actionSettings.triggered.connect(self.open_settings)
		ui.actionGoto_market.triggered.connect(self.goto_market)
		
		ui.actionTransfer.triggered.connect(self.show_transfer)
		ui.actionSell.triggered.connect(self.show_sell)
		
		ui.transferButton.clicked.connect(self.make_transfer)
		ui.sellButton.clicked.connect(self.make_limit_order)
		
		#ui.sellOpenMarketButton.clicked.connect(self.sell_open_market)
		self.uiAssetsMarketLink(
			self.ui.sellAssetCombo,
			self.ui.buyAssetCombo,
			None, None,
			self.ui.sellOpenMarketButton)
		
		ui.actionAccounts.triggered.connect(self.toggle_accountbar)
		ui.actionAdvancedOptions.triggered.connect(self.toggle_advancedoptions)
		
		ui.actionAbout.triggered.connect(self.show_about)
		
		
		ui.actionResync_accounts.triggered.connect(self.mergeAccounts)
		ui.actionWipeResync_accounts.triggered.connect(self.evilMergeAccounts)
		ui.actionRedownload_assets.triggered.connect(self.evilDownloadAssets)
		ui.actionWipeResync_history.triggered.connect(self.evilDownloadHistory)
		ui.actionResync_history.triggered.connect(self.massResync)
		ui.actionResync_orders.triggered.connect(self.massResync)

		self.log_record.connect(self.add_log_record)

		#
		self.setupRecentWalletsMenu()
		#
		self.account_names = set()
		self.contact_names = set("")
		self.open_accounts = set()
		
		self.stash = [ ]
		
		self.init_blind()
		
		self.init_assets()
		
		self.init_markets()
		
		self.init_gateway()
		
		self.init_contacts()
		
		self.connector = RemoteFetch()
		self.background_update.connect(self.on_connector_update)
		self._connecting = False
		self._user_intent = 0
		
		qmenu(self.ui.accountsList, self.show_account_submenu)
		
		self.ui.accountsList.itemClicked.connect(self.activate_account)
		self.ui.accountsList.itemActivated.connect(self.activate_account)
		self.ui.statusAccounts.currentIndexChanged.connect(self.activate_account)

		self.uiExpireSliderLink(self.ui.sellexpireEdit, self.ui.sellexpireSlider)

		#self.ui.sellerBox.currentIndexChanged.connect(self.mini_reacc)
		#self.ui.transferFromAccount.currentIndexChanged.connect(self.mini_reacc)
		self.uiAccountAssetLink(self.ui.transferFromAccount, self.ui.transferAsset)
		self.uiAccountAssetLink(self.ui.transferFromAccount, self.ui.transferFeeAsset)
		self.uiAccountAssetLink(self.ui.sellerBox, self.ui.sellAssetCombo)
		self.uiAccountAssetLink(self.ui.sellerBox, self.ui.buyAssetCombo)
		self.uiAccountAssetLink(self.ui.sellerBox, self.ui.sellFeeAsset)
		
		self.uiAssetLink(self.ui.transferAmount, self.ui.transferAsset)
		self.uiAssetLink(self.ui.sellAmountSpin, self.ui.sellAssetCombo)
		self.uiAssetLink(self.ui.buyAmountSpin, self.ui.buyAssetCombo)
		
		self.init_trxbuffer()
		
		self.ui.consoleList.setColumnCount(3)
		stretch_table(self.ui.consoleList, hidehoriz=True)
		self.debug_timer = qtimer(1000, self.refreshUi_console)
		
		self.emptyPix = QtGui.QPixmap(24, 24)
		self.emptyPix.fill( QtGui.QColor(0, 0, 0, 0) )
		self.emptyIcon = QtGui.QIcon()
		
		self.notes_timer = qtimer(2500, self.mergeNotes)
		
		
		# tag tabs:
		j = -1
		for tag in [ "markets", "gateways", "blind", "ops", "console", "contacts" ]:
			j += 1
			tab = self.ui.tabWidget.widget(j)
			tab._tags = [ "^" + tag ]
		
		
		self.config_triggers = { }
		
		def gettab(tag):
			return self.findTab(QtGui.QWidget, tag)
		
		self.uiActionFrontLink(self.ui.actionBalances, DashboardTab)
		self.uiActionFrontLink(self.ui.actionHistory, HistoryTab)
		self.uiActionFrontLink(self.ui.actionOrders, OrderTab)
		
		self.uiSingletonActionLink(
			gettab("^contacts"),
			self.ui.actionContacts,
			"ui_showcontacts",
			False)
		
		self.uiSingletonActionLink(
			gettab("^console"),
			self.ui.actionConsole,
			"ui_showconsole",
			False)
		
		#self.uiSingletonActionLink(
		#	gettab("^assets"),
		#	self.ui.actionAssets,
		#	"ui_showassets",
		#	True)
		
		self.uiSingletonActionLink(
			gettab("^markets"),
			self.ui.actionMarkets,
			"ui_showmarkets",
			True)
		
		self.uiSingletonActionLink(
			gettab("^gateways"),
			self.ui.actionGateways,
			"ui_showgateways",
			True)
		
		self.uiSingletonActionLink(
			gettab("^blind"),
			self.ui.actionBlinds,
			"ui_showblind",
			False)
		
		#self.ui.stackFrame.setVisible(False)
		#self.hideTab(gettab("^ops"))
		self.uiSingletonActionLink(
			gettab("^ops"),
			self.ui.actionShowOperations,
			"ui_showoperations",
			False)
		
		self.showAccountBar(False)
		self.ui.txFrame.hide()
		
##		QtGui.QApplication.processEvents( QtCore.QEventLoop.ExcludeUserInputEvents )
		self.resize( self.sizeHint() )
		QtCore.QTimer.singleShot(1, self.fixSize)
		
		app().aboutToQuit.connect(self.abort_everything)
		
	
	def fixSize(self):
		self.resize( self.sizeHint() )
	
	def setupStatusBar(self):
		statusbar = self.ui.statusbar
		self.ui.statusAccounts = QtGui.QComboBox()
		self.ui.statusAccounts.setMinimumSize(120, 20)
		
		self.ui.statusWallet = QtGui.QLabel()
		self.ui.statusWallet.setText("")
		
		self.ui.statusLock = QtGui.QPushButton()
		self.ui.statusLock.setText("")
		self.ui.statusLock.setFlat(True)
		self.ui.statusLock.setMaximumSize(32, 32)
		
		self.ui.statusNetwork = QtGui.QPushButton()
		self.ui.statusNetwork.setText("")
		self.ui.statusNetwork.setFlat(True)
		self.ui.statusNetwork.setMaximumSize(32, 32)
		
		self.ui.statusProxy = QtGui.QLabel()
		self.ui.statusProxy.setText("")
		
		self.ui.statusText = QtGui.QLabel()
		self.ui.statusText.setText("")
		statusbar.addWidget(self.ui.statusText, 10)
		
		statusbar.addWidget(self.ui.statusAccounts)
		#statusbar.addWidget(self.ui.statusWallet)
		statusbar.addWidget(self.ui.statusLock)
		statusbar.addWidget(self.ui.statusNetwork)
		#statusbar.addWidget(self.ui.statusProxy)
		
		self.ui.minimenuWallet = menu = QtGui.QMenu()
		self.ui.actionLock_wallet_2 = (
			qaction(self, menu, "Lock", self.lock_wallet) )
		self.ui.actionUnlock_wallet_2 = (
			qaction(self, menu, "Unlock", self.unlock_wallet) )
		self.ui.minimenuNetowrk = menu = QtGui.QMenu()
		self.ui.actionConnect_2 = (
		qaction(self, menu, "Connect", self.connect_to_node) )
		self.ui.actionDisconnect_2 = (
		qaction(self, menu, "Disconnect", self.disconnect_from_node) )
		menu.addSeparator()
		qaction(self, menu, "Network Settings...", self.open_network_settings)
		self.ui.statusLock.setMenu(self.ui.minimenuWallet)
		self.ui.statusNetwork.setMenu(self.ui.minimenuNetowrk)
		#qmenu(self.ui.statusLock, self.show_lock_submenu)
		#qmenu(self.ui.statusNetwork, self.show_network_submenu)
	
	def setupRecentWalletsMenu(self):
		menu = self.ui.menuOpen_Recent
		lst = list(RecentWallets.recent)
		for item in lst:
			qa = qaction(self, menu, str(item), self.open_recent_wallet)
	def open_recent_wallet(self):
		qa = self.sender()
		path = qa.text()
		app().reopen(path)
	
	def uiAssetsMarketLink(self, a, b, _a, _b, btn):
		a._bidask = (_a, _b)
		a._other = b
		a._btn = btn
		a._forward = True
		b._bidask = (_a, _b)
		b._other = a
		b._btn = btn
		b._forward = False
		btn._a = a
		btn._b = b
		#a.textEdited.connect(self.uiAssetsMarket_perform)
		a.editTextChanged.connect(self.uiAssetsMarket_perform)
		a.currentIndexChanged.connect(self.uiAssetsMarket_perform)
		#a.textEdited.connect(self.uiAssetsMarket_perform)
		b.editTextChanged.connect(self.uiAssetsMarket_perform)
		b.currentIndexChanged.connect(self.uiAssetsMarket_perform)
		btn.clicked.connect(self.uiAssetsMarket_click)
	
	def uiAssetsMarket_perform(self):
		o = self.sender()
		if (o._forward):
			a = o
			b = o._other
		else:
			b = o
			a = o._other
		btn = o._btn
		
		asset_name_a = any_value(a)
		asset_name_b = any_value(b)
		on = True
		if not asset_name_a or not asset_name_b:
			on = False
		if asset_name_a == asset_name_b:
			on = False
		
		btn.setEnabled(on)
	
	def uiAssetsMarket_click(self):
		btn = self.sender()
		a = btn._a
		b = btn._b
		
		asset_name_a = any_value(a)
		asset_name_b = any_value(b)
		
		if not asset_name_a:
			showerror("Select asset to sell")
			return
		if not asset_name_b:
			showerror("Select asset to buy")
			return
		if asset_name_a == asset_name_b:
			showerror("Select different assets")
			return
		try:
			self.openMarket(asset_name_a, asset_name_b)
		except Exception as error:
			showexc(error)
			return
	
	
	def uiActionFrontLink(self, qact, find_class):
		qact._linkedClass = find_class
		qact.triggered.connect(self.uiActionFront_perform)
	
	def uiActionFront_perform(self):
		account = self.activeAccount
		qact = self.sender()
		find_class = qact._linkedClass
		tab = self.findTab(find_class, account.name)
		if not tab:
			log.warn("Tab not found %s %s", find_class, account.name)
			return
		self.setTabVisible(tab, True)
	
	def uiSingletonActionLink(self, tab, qact, config_key, default):
		qact._linkedTab = tab
		qact._configKey = config_key
		qact._default = default
		qact.setChecked(default)
		self.setTabVisible(tab, default)
		qact.triggered.connect(self.uiSingletonAction_perform)
		self.config_triggers[config_key] = qact
	
	def uiSingletonAction_perform(self):
		qact = self.sender()
		tab = qact._linkedTab
		config_key = qact._configKey
		default = qact._default
		val = qact.isChecked()
		self.iso.bts.config[config_key] = val
		self.setTabVisible(tab, val)
	
	expire_ranges = [
		"1m", "5m", "10m",
		"15m", "30m", "45m",
		"1h", "1h30m", 
		"2h", "3h", "4h", "5h", "6h",
		"7h", "8h", "9h", "10h", "11h",
		"12h",
		"1 day", "2 days", "3 days",
		"4 days", "5 days", "6 days",
		"1 week", "2 weeks", "3 weeks",
		"1 month", "2 months", "3 months",
		"4 months", "5 months", "6 months",
		"7 months", "8 months", "9 months",
		"10 months", "11 months",
		"1 year",
	]
	def uiExpireSliderLink(self, expEdit, expSlider, emit=False):
		expSlider._linkedEdit = expEdit
		expSlider._reemit = emit
		expSlider.setMinimum( 0 )
		expSlider.setMaximum( len(self.expire_ranges)-1 )
		expSlider.valueChanged.connect(self.uiExpireSlider_perform)
	
	def uiExpireSlider_perform(self):
		expSlider = self.sender()
		expEdit = expSlider._linkedEdit
		reemit = expSlider._reemit
		
		v = expSlider.value()
		s = self.expire_ranges[v]
		expEdit.setText(s)
		if reemit:
			expEdit.editingFinished.emit()
	
	def uiAccountAssetLink(self, accCombo, symCombo):
		if not hasattr(accCombo, '_linkedAssets'):
			accCombo._linkedAssets = [ ]
		accCombo._linkedAssets.append( symCombo )
		accCombo.currentIndexChanged.connect(self.uiAccountAssetLink_perform)
		
	
	def uiAccountAssetLink_perform(self):
		accCombo = self.sender()
		symCombos = accCombo._linkedAssets
		account_id = accCombo.currentText()
		if not len(account_id):
			return
		
		try:
			account = self.iso.getAccount(account_id)
		except:
			import traceback
			traceback.print_exc()
			return
		
		for symCombo in symCombos:
			symCombo.clear()
		
		balances = self.iso.getBalances(account)
		for b in balances:
			for symCombo in symCombos:
				symCombo.addItem(b.symbol)
	
	def uiAssetLink(self, amtSpin, symCombo):
		
		symCombo._linkedBox = amtSpin
		symCombo.currentIndexChanged.connect(self.uiAssetLink_perform)
		symCombo.editTextChanged.connect(self.uiAssetLink_perform)
	
	def uiAssetLink_perform(self):
		symCombo = self.sender()
		amtSpin = symCombo._linkedBox
		token = symCombo.currentText().upper()
		if not token:
			return
		try:
			asset = self.iso.getAsset(token)
		except Exception as error:
			log.error("Unable to figure out asset %s", token)
			#showexc(error)
			return
		
		amtSpin.setDecimals( int(asset['precision']) )
		amtSpin.setMaximum( float(asset['options']['max_supply']) )
	
	def add_log_record(self, record):
		msg = record.getMessage()
		ce = self.ui.consoleEdit
		tc = ce.textCursor()
		tc.movePosition(QTextCursor.End)
		tc.insertText(msg+"\n")
		ce.setTextCursor(tc)
	
	def showAccountBar(self, on):
		if on:
			self.ui.accountsList.setVisible(True)
			self.ui.statusAccounts.setVisible(False)
		else:
			self.ui.accountsList.setVisible(False)
			self.ui.statusAccounts.setVisible(True)
		self.ui.actionAccounts.setChecked(on)
		try:
			self.iso.bts.config["ui_showaccounts"] = on
		except:
			pass
	
	def init_operations(self):
		self.opstack = StackLinker(
		self.ui.opStack, [
			(self.ui.viewOpTransfer, self.ui.actionTransfer, "!transfer"),
			(self.ui.viewOpSell, self.ui.actionSell, "!sell"),
		], lambda: self.tagToFront("^ops"))
		self.opstack.setPage(0)
		
		on_spin(self.ui.sellAmountSpin, self.sell_main_amount_changed)
		on_spin(self.ui.buyAmountSpin, self.sell_alt_amount_changed)
		# also, when asset type changes
		on_combo(self.ui.sellAssetCombo, self.sell_alt_amount_changed)
		on_combo(self.ui.buyAssetCombo, self.sell_main_amount_changed)
		
		self.sell_estimater = RemoteFetch()
		
		#self.ui.ainAmt"].valueChanged.connect(self.main_amount_changed)
		#form["mainAmt"].valueChanged.connect(self.main_amount_changed)
	
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
		iso = self.iso
		
		mtype = sell_asset + ":" + buy_asset
		from bitshares.market import Market
		
		market = Market(mtype, blockchain_instance=self.iso.bts)
		tick = market.ticker()
		
		highestBid = float(tick['highestBid']) #        return self["price"]
		lowestAsk = float(tick['lowestAsk']) #        return self["price"]
		
		if buy_amount:
			amt = float(buy_amount)
			re = amt / highestBid
			#self.ui.sellAmountSpin.setValue( re )
		
		if sell_amount:
			amt = float(sell_amount)
			re = amt * highestBid
			#self.ui.buyAmountSpin.setValue( re )
		
		#self.ui.sellComment.setText( str(tick) )
		
		return (re, buy_amount, sell_amount)
	
	def sell_estimated(self, uid, args):
		(re, buy_amount, sell_amount) = args
		
		if buy_amount:
			elem = self.ui.sellAmountSpin
		
		if sell_amount:
			elem = self.ui.buyAmountSpin
		
		elem.blockSignals(True)
		elem.setValue( re )
		elem.blockSignals(False)
		
	def sell_estimation_failed(self, uid, error):
		pass
	
	#def opToFront(self, tag):
	#	self.opstack.setPageByTag(tag)
	
	
	
	def prepareAdvancedMode(self):
		self.EDITABLES = [
			self.ui.transferFromAccount,
			self.ui.transferAsset,
			self.ui.sellerBox,
			self.ui.sellAssetCombo,
			self.ui.blindFromAsset,
			self.ui.blindToAsset,
			self.ui.blindAsset,
		]
		self.VISIBLES = [
			self.ui.transferFeeAsset,
			self.ui.transferFeeLabel,
			self.ui.sellFeeAsset,
			self.ui.sellFeeLabel,
			self.ui.bridgeDetails,
			self.ui.blindFromFeeAssetLabel,
			self.ui.blindFromFeeAsset,
			self.ui.blindToFeeAssetLabel,
			self.ui.blindToFeeAsset,
			self.ui.blindFeeAssetLabel,
			self.ui.blindFeeAsset
		]
	
	def setAdvancedMode(self, on):
		for widget in self.EDITABLES:
			widget.setEditable(on)
		for widget in self.VISIBLES:
			widget.setVisible(on)
		self.ui.actionAdvancedOptions.setChecked(on)
		self.iso.bts.config["ui_advancedmode"] = on
	
	def late_inject_advanced_controls(self, editables, visibles):
		on = self.is_advancedmode()
		for widget in editables:
			self.EDITABLES.append(widget)
			widget.setEditable(on)
		for widget in visibles:
			self.VISIBLES.append(widget)
			widget.setVisible(on)
	
	def mergeNotes(self):
		if not self.iso:
			return
		tabs = self._allTabs()
		dump = self.iso.flush_notes()
		tabs_need_resync = [ ]
		for idx, package in dump:
			if idx >= 100:
				for tab in tabs:
					if isinstance(tab, MarketTab):
						if ("!" + str(idx)) in tab._tags:
							tabs_need_resync.append(tab)
							break
				continue
			for notes in package:
				for note in notes:
					if isinstance(note, str):
						#print("Skipping", note)
						continue
					#print("Check out:", idx, note)
					id = note['id']
					if id[:4] == "2.6.":
						tab = self.on_account_note(note)
						if tab:
							tabs_need_resync.append(tab)
					if id[:4] == "2.5.":
						self.on_balance_note(note)
					#from pprint import pprint
					#pprint(note)
					#break
		tabs_need_resync = set(tabs_need_resync)
		for tab in tabs_need_resync:
			tab.resync()
	
	def sell_open_market(self):
		asset_name_a = self.ui.sellAssetCombo.currentText()
		asset_name_b = self.ui.buyAssetCombo.currentText()
		
		if not asset_name_a:
			showerror("Select asset to sell")
			return
		if not asset_name_b:
			showerror("Select asset to buy")
			return
		if asset_name_a == asset_name_b:
			showerror("Select different assets")
			return
		try:
			self.openMarket(asset_name_a, asset_name_b)
		except Exception as error:
			showexc(error)
			return
	
	
	def openMarket(self, asset_name_a, asset_name_b, to_front=True):
		
		if self.iso.offline:
			raise ResourceUnavailableOffline("Market " + asset_name_a + ":" + asset_name_b)
		asset_a = self.iso.getAsset(asset_name_a)
		asset_b = self.iso.getAsset(asset_name_b)
		
		pair = (asset_a, asset_b)
		tag = asset_a["symbol"] + ":" + asset_b["symbol"]
		
		self.restoreTab(MarketTab, self.addMarketTab, pair, tag, to_front=to_front)
	
	def closeMarket(self, tag):
		self.destroyTab(MarketTab, tag)
	
	def swapMarket(self, tag):
		a, b = str.split(tag, ":")
		self.closeMarket(tag)
		self.openMarket(b, a, to_front=True)
	
	def on_account_note(self, note):
		#from pprint import pprint
		#print("Account update:")
		#pprint(note)
		
		account_id = note['owner']
		try:
			account = self.iso.getAccount(account_id, force_local=True)
		except:
			account = None
		
		if not account:
			#print("Could not locally resolve account %s to perform sync" % (str(account_id)))
			return None
		
		log.info("Update for account %s", account.name)
		tab = self.findTab(HistoryTab, account.name)
		
		return tab
		
		if tab:
			print("Have a history tab for it:")
			tab.mergeHistory_async(self.iso, account)
		else:
			print("No history tab for it")
	
	def on_balance_note(self, note):
		account_id = note["owner"]
		asset_id = note["asset_type"]
		amount = note["balance"]
		
		try:
			account = self.iso.getAccount(account_id, force_local=True)
		except:
			account = None
		if not account:
			#print("Could not locally resolve account %s to inject balance" % (str(account_id)))
			return
		log.info("New balance for account %s", account.name)
		
		try:
			asset = self.iso.getAsset(asset_id)
		except Exception as error:
			log.error("Failed to getAsset %s, aborting injection; error %s", asset_id, str(error))
			return
		
		account = self.iso.injectBalance(account_id, asset["symbol"], amount)
		balances = self.iso.getBalances(account, force_remote=False)
		
		dash = self.findTab(DashboardTab, account_id)
		if dash:
			dash.refresh_balances(balances)
		
		orders = self.findTab(OrderTab, account_id)
		if orders:
			orders.refresh_balances(balances)
		
	def open_settings(self, page=0):
		if not(self.iso.bts.wallet):
			showerror("No wallet file open")
			return False
		win = SettingsWindow(isolator=self.iso)
		win.setPage(page)
		win.exec_()
		self.updateUIfromConfig()
		self.perhaps_autoconnect()
		self.gateways_populated = False
		return True
	
	def open_network_settings(self):
		return self.open_settings(1)
	
	def open_memowindow(self):
		win = MemoWindow(isolator=self.iso,
			accounts=self.account_names,
			contacts=self.contact_names,
			activeAccount=self.activeAccount,
		)
		win.exec_()
	
	def open_createassetwindow(self):
		win = AssetWindow(isolator=self.iso, mode="create",
			accounts=self.account_names,
			account=self.activeAccount,
			)
		win.exec_()
	
	def goto_market(self):
		input, ok = QtGui.QInputDialog.getText(
			None, 'Go to Market',
			'Market name, like BTS:BTC')#, QtGui.QLineEdit.Password)
		
		if not ok:
			return False
		
		if not input:
			return False
		
		if not ":" in input:
			return False
		
		a, b = str.split(input, ":")
		try:
			self.openMarket(a, b)
		except Exception as error:
			showexc(error)
			return False
		return True
	
	def toggle_accountbar(self):
		self.showAccountBar( self.ui.actionAccounts.isChecked() )
	
	def toggle_advancedoptions(self):
		self.setAdvancedMode( self.ui.actionAdvancedOptions.isChecked() )
	
	def is_advancedmode(self):
		return self.ui.actionAdvancedOptions.isChecked()
	
	def show_transfer(self):
		self.OTransfer()
	def show_sell(self):
		self.OSell()
	
	def show_about(self):
		info = library_versions(platform=True)
		showdialog(UNIX_NAME+" "+VERSION, title="About",
		additional="Python BitShares Wallet", details=info,
		icon=':/images/images/logo.png')
	
	def show_account_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Show Account", self.activate_account)
		qaction(self, menu, "Hide Account", self.deactivate_account)
		qaction(self, menu, "Remove Account...", self._remove_account)
		menu.addSeparator()
		qaction(self, menu, "Export Private Keys...", self._export_account_keys)
		qaction(self, menu, "Show Private Keys", self._show_account_keys)
		qaction(self, menu, "Sweep Private Keys...", self._sweep_account_keys)
		qmenu_exec(self.sender(), menu, position)
	
	def activate_account(self):
		box = self.sender()
		if (isinstance(box, QtGui.QAction)):
			box = self.ui.accountsList
		if (isinstance(box, QtGui.QComboBox)):
			account_name = box.currentText()
			if not account_name:
				return
		else:
			if not box.currentIndex().isValid():
				return
			account_name = box.currentItem().text()
		
		tab_index = self.ui.tabWidget.currentIndex()
		
		self.hide_accounts([account_name])
		
		print("--- ", account_name)
		self.setActiveAccount(account_name)
		print("----- activated")
		
		self.ui.tabWidget.setCurrentIndex(tab_index)
	
	def hide_accounts(self, unless=[ ]):
		n = self.ui.tabWidget.count()
		for i in range(n, -1, -1):
			tab = self.ui.tabWidget.widget(i)
			if not(hasattr(tab, '_tags')):
				continue
			if not("#account" in tab._tags):
				continue
			skip = False
			for tag in tab._tags:
				if tag in unless:
					skip = True
					break
			if skip:
				continue
			
			self.hideTab(tab)
	
	def deactivate_account(self):
		self.hide_accounts()
	
	def _export_account_keys(self):
		box = self.ui.accountsList
		if not box.currentIndex().isValid():
			return
		account_name = box.currentItem().text()
		
		path, _ = QtGui.QFileDialog.getSaveFileName(self, 'Export Private Keys', account_name + "_keys.json", "key dump (*.json)")
		if not path:
			return False
		
		try:
			with self.iso.unlockedWallet(
				reason='Export Private Keys for ' + account_name
			) as w:
				pubs = self.iso.getLocalAccountKeys(account_name)
				priv = self.iso.getPrivateKeyForPublicKeys(pubs)
		except WalletLocked:
			return
		except Exception as exc:
			showexc(exc)
			return
		
		array = [ ]
		for i in range(0, len(pubs)):
			array.append( [ pubs[i], priv[i] ] )
		
		import json
		data = json.dumps(array)
		with open(path, "w") as f:
			f.write(data)
		
		return True
	
	def _show_account_keys(self):
		box = self.ui.accountsList #sender()
		if not box.currentIndex().isValid():
			return
		account_name = box.currentItem().text()

		try:
			with self.iso.unlockedWallet(
				reason='View Private Keys for ' + account_name
			) as w:
				pubs = self.iso.getLocalAccountKeys(account_name)
				priv = self.iso.getPrivateKeyForPublicKeys(pubs)
		except WalletLocked:
			return
		except Exception as exc:
			showexc(exc)
			return
		
		priv_txt = "\n".join(priv)
		showdialog("Private keys for account",
			additional=account_name,
			details=priv_txt, min_width=240)
	
	
	def add_account(self):
		try:
			with self.iso.unlockedWallet() as w:
				self._add_account()
		except WalletLocked:
			showerror("Can't add account to a locked wallet")
		except Exception as error:
			showexc(error)
	
	def _sweep_account_keys(self):
		box = self.ui.accountsList
		if not box.currentIndex().isValid():
			return
		account_name = box.currentItem().text()
		
		try:
			with self.iso.unlockedWallet() as w:
				n = self._sweep_keys(account_name)
		except WalletLocked:
			showerror("Can't add account to a locked wallet")
			return
		except Exception as error:
			showexc(error)
			return
		
		if n == 1:
			showmsg("Key has been replaced")
		else:
			showmsg("%d keys have been replaced" % n)
	
	def _remove_account(self):
		box = self.ui.accountsList
		if not box.currentIndex().isValid():
			return
		account_name = box.currentItem().text()
		if not(askyesno("If you don't have some means to restore this account, you will permamentely lose access to it.\n\nAre you sure you want to remove account %s from this wallet?" % account_name)):
			return
		try:
			self.iso.bts.wallet.removeAccount(account_name)
			self.iso.store.accountStorage.delete(account_name)
			#self.iso.store.accountStorage.update(account_name, "keys", 0)
			self.remove_account_name(account_name)
			
			showmessage("Account removed")
		except Exception as exc:
			showexc(exc)
	
	def need_autoconnect(self, ignore_state=False):
		config = self.iso.bts.config
		nodeUrl = config.get('node', None)
		ac = config.get('autoconnect', True)
		#print("AUTOCONN?", nodeUrl, ac)
		if not ac or not nodeUrl:
			return False
		if ignore_state:
			return True
		if self.iso.is_connected():
			return False
		if self.iso.is_connecting():
			return False
		return True
	
	def perhaps_cyclenode(self):
		config = self.iso.bts.config
		nodeUrl = config.get('node', None)
		doit = config.get('cyclenodes', False)
		if not doit:
			return
		store = self.iso.store.remotesStorage
		remotes = store.getRemotes(store.RTYPE_BTS_NODE)
		if len(remotes) == 0:
			return False
		use_next = False
		for remote in remotes:
			if use_next:
				nodeUrl = remote["url"]
				use_next = False
				break
			if remote["url"] == str(nodeUrl):
				use_next = True
		if use_next or not nodeUrl:
			nodeUrl = remotes[0]["url"] # first one!
		config['node'] = nodeUrl
		log.info("Cycled to node %s", nodeUrl)
		return nodeUrl
	
	def perhaps_autoconnect(self, ignore_state=False):
		if not(self.need_autoconnect(ignore_state)):
			return False
		self.connect_to_node(auto=True)
		return True
	
	def _connect(self, nodeUrl, proxyUrl, request_handler=None):
		nodeUrl = str(nodeUrl)
		
		self._connecting = True
		self.iso.connect(nodeUrl, proxy=proxyUrl, num_retries=3, request_handler=request_handler)
	
	def _connect_event(self, uid, ps, data):
	#	if type(data) is int:
	#		return
	#	ws, desc, error = data
	#	self.background_update.emit(0, desc, (ws, error))
		self.refreshUi_wallet()
	
	def on_connector_update(self, id, tag, data_error):
		if id != 0:
			return
		(data, error) = data_error
		log.info("<%s>", tag)
		#print("OCU", id, tag, data)
		ws = data
		desc = tag
		if ws.connected and (desc == "connected" or desc == "reconnected"):
			self.connection_established(0, None)
		if desc == "failed":
			self.iso.offline = True
			#self.connection_failed(0, error)
		if desc == "disconnected" or desc == "lost":
			self.iso.offline = True
			self.connection_lost(0)
		if desc == "connecting" or desc == "reconnecting":
			self._connecting = True
		else:
			self._connecting = False
		self.refreshUi_wallet()
	
	def connect_to_node(self, auto=True):
		self._connecting = True
		self._user_intent = int(bool(not auto))
		config  = self.iso.bts.config
		nodeUrl = config.get('node', None)
		proxyUrl = self.iso.get_proxy_config()
		
		if not nodeUrl:
			showerror("No public node selected")
			self.open_network_settings()
			return
		
		#self.abort_everything(disconnect=True)
		#self._connect()
		self.connector.fetch(self._connect,
			nodeUrl, proxyUrl,
			ready_callback=self.connection_established,
			error_callback=self.connection_failed,
		#	ping_callback=self.refreshUi_wallet,
			ping_callback=self._connect_event,
			description="Connecting")
		log.info("* Connecting...")
	
	
	def connection_established(self, uid, result):
		self._connecting = False
		log.info("* Connection established")
		
		self.iso.offline = False
		self.iso.subscribed_accounts = set()
		self.iso.subscribed_markets = set()
		self.massDesync()
		#self.mergeAccounts()
		
		if self.iso.store.assetStorage.countEntries() < 2:
			self.download_assets()
		self.download_markets()
		self.massResync()
		
		#self.start_periodic_updater()
		
		self.refreshUi_wallet()
	
	def connection_failed(self, uid, error):
		self._connecting = False
		log.info("* Connection failed %s", str(error))
		self.iso.offline = True
		self.refreshUi_wallet()
		self.abort_everything(disconnect=False, wait=True)
		if self._user_intent:
			self._user_intent -= 1
			showerror("Connection failed", additional=error)
		self.perhaps_cyclenode()
		self.perhaps_autoconnect(ignore_state=True)
	
	def connection_lost(self, uid):
		self._connecting = False
		log.info("* Connection lost")
		self.iso.offline = True
		self.refreshUi_wallet()
		##Request.shutdown(timeout=10)
		self.abort_everything(disconnect=True, wait=True)
	
	def disconnect_from_node(self):
		log.info("* Disconnecting...")
		self._connecting = False
		#self.refreshUi_wallet()
		#self.iso.disconnect()
		self.abort_everything(disconnect=True)
		self.refreshUi_wallet()
	
	def abort_everything(self, disconnect=True, wait=True):
		app = QtGui.QApplication.instance()
		log.debug("1. emit abort_everything")
		app.abort_everything.emit()
		#
		if disconnect or wait:
			log.debug("( cancel threads )")
			Request.cancel_all()
		#
		if self.iso and disconnect:
			log.debug("2. disconnect")
			self.iso.disconnect()
		#
		if wait:
			log.debug("3. shutdown threads")
			Request.shutdown(timeout=10)
	
	
	def buffering(self):
		return self.ui.txFrame.isVisible()
	
	def make_upgrade(self):
		if not self.activeAccount:
			return
		
		account_name = self.activeAccount['name']
		try:
			trx = QTransactionBuilder.QUpgradeAccount(
				account_name,
				#fee_asset=fee_asset,
				isolator=self.iso)
		except BaseException as error:
			showexc(error)
	
	def make_limit_order(self):
		account_from = self.ui.sellerBox.currentText()
		sell_asset_name = self.ui.sellAssetCombo.currentText()
		sell_asset_amount = self.ui.sellAmountSpin.value()
		buy_asset_name = self.ui.buyAssetCombo.currentText()
		buy_asset_amount = self.ui.buyAmountSpin.value()
		expire_seconds = deltasec(self.ui.sellexpireEdit.text())
		expire_fok = self.ui.fokCheckbox.isChecked()
		fee_asset = anyvalvis(self.ui.sellFeeAsset, None)#.currentText()
		
		buffer = self.ui.txFrame.isVisible()
		
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
				isolator=self.iso)
			if buffer:
				self._txAppend(*v)
			else:
				QTransactionBuilder._QExec(self.iso, v)
		except BaseException as error:
			showexc(error)
			return False
		return True
	
	def make_transfer(self):
		account_from = self.ui.transferFromAccount.currentText()
		account_to = self.ui.transferToAccount.currentText()
		asset_name = self.ui.transferAsset.currentText()
		asset_amount = self.ui.transferAmount.text()
		memo_text = self.ui.transferMemo.toPlainText()
		fee_asset = anyvalvis(self.ui.transferFeeAsset, None)#.currentText()
		buffer = self.buffering()
		
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
				self._txAppend(*v)
			else:
				QTransactionBuilder._QExec(self.iso, v)
		except BaseException as error:
			showexc(error)
			return False
		return True
	
	def openAccount(self, account_name):
		if account_name in self.open_accounts:
			return False
		self.open_accounts.add(account_name)
		return True
	
	def closeAccount(self, account_name):
		if account_name in self.open_accounts:
			return False
		self.open_accounts.remove(account_name)
		return True
	
	def highlight_account(self, account_name=None):
		if account_name is None:
			account_name = self.activeAccount.name
		
		table = self.ui.accountsList
		n = table.count()
		for i in range(0, n):
			item = table.item(i)
			font = item.font()
			font.setBold(False)
			name = item.text()
			if name == account_name:
				font.setBold(True)
			item.setFont(font)
		
		self.ui.statusAccounts.blockSignals(True)
		set_combo(self.ui.statusAccounts, account_name)
		self.ui.statusAccounts.blockSignals(False)
	
	def loadAccounts(self):
		#accs = []
		accs = self.iso.getCachedAccounts()
		
		for acc in accs:
			self.add_account_name(acc)
		
		if len(accs) == 1:
			self.setActiveAccount(accs[0])
		
		return len(accs)
	
	def setActiveAccount(self, account_name):
		
		self.activeAccount = self.iso.getAccount(account_name)
		
		self.refilter_assets()
		
		fresh = self.openAccount(account_name) # does nothing
		if fresh:
			self.download_markets()
		
		self.restoreTab(DashboardTab, self.addDashboardTab, self.activeAccount, account_name)
		self.restoreTab(HistoryTab, self.addHistoryTab, self.activeAccount, account_name)
		self.restoreTab(OrderTab, self.addOrderTab, self.activeAccount, account_name)
		
		self.openExternalHistory(self.iso, self.activeAccount)
		
		self.highlight_account(account_name)
		
		self.refreshUi_title()
	
	def massResync(self):
		tabs = self._allTabs()
		
		for tab in tabs:
			if hasattr(tab, "resync"):
				tab.resync()
	
	def massDesync(self):
		tabs = self._allTabs()
		
		for tab in tabs:
			if hasattr(tab, "desync"):
				tab.desync()
	
	def addMarketTab(self, pair, tag):
		ui = self.ui
		
		tab = MarketTab(
			asset_a=pair[0],
			asset_b=pair[1],
			isolator=self.iso,
			ping_callback=self.refreshUi_ping)
		
		tab._icon = qicon(":/icons/images/market.png")
		
		split = str.split(tag, ":")
		retag = split[1]+":"+split[0]
		
		tab._tags = [
			tag,
			retag,
			'#market',
		]
		tab._refreshTitle()
		
		# Late comers!
		self.uiAccountAssetLink(tab.ui.buyAccount, tab.ui.buyFeeAsset)
		self.uiAccountAssetLink(tab.ui.sellAccount, tab.ui.sellFeeAsset)
		self.uiExpireSliderLink(tab.ui.buyExpireEdit, tab.ui.buyExpireSlider)
		self.uiExpireSliderLink(tab.ui.sellExpireEdit, tab.ui.sellExpireSlider)
		self.late_inject_account_box(tab.ui.buyAccount)
		self.late_inject_account_box(tab.ui.sellAccount)
		if self.activeAccount:
			set_combo(tab.ui.buyAccount, self.activeAccount["name"])
			set_combo(tab.ui.sellAccount, self.activeAccount["name"])
		self.late_inject_asset_box(tab.ui.buyFeeAsset)
		self.late_inject_asset_box(tab.ui.sellFeeAsset)
		self.late_inject_advanced_controls(
			editables=[
				tab.ui.buyAccount,
				tab.ui.sellAccount,
			],
			visibles=[
				tab.ui.buyFeeLabel,
				tab.ui.buyFeeAsset,
				tab.ui.sellFeeLabel,
				tab.ui.sellFeeAsset,
			]
		)
		config = self.iso.bts.config
		expire_seconds = config.get("order-expiration", 3600*24)
		expire_fok = bool(config.get("order-fillorkill", False))
		tab.ui.sellExpireEdit.setText(deltainterval(expire_seconds))
		tab.ui.buyExpireEdit.setText(deltainterval(expire_seconds))
		tab.ui.buyFOK.setChecked(bool(expire_fok))
		tab.ui.sellFOK.setChecked(bool(expire_fok))
		
		tab.resync()
		
		return tab
	
	def addHistoryTab(self, account, tag):
		ui = self.ui
		
		tab = HistoryTab(ping_callback=self.refreshUi_ping)
		
		tab._tags = [
			account.name,
			account.id,
			"#account",
		]
		
		tab._title = _translate("MainWindow", "History", None)
		tab._icon = None
		
		tab.openHistory(self.iso, account)
#		tab.mergeHistory(self.iso, account)
		
		return tab
	
	def addOrderTab(self, account, tag):
		ui = self.ui
		
		tab = OrderTab(ping_callback=self.refreshUi_ping)
		
		tab._tags = [
			account.name,
			account.id,
			"#account",
		]
		
		tab._title = _translate("MainWindow", "Exchange", None)
		tab._icon = None
		
		# Later comers!
		self.late_inject_asset_box(tab.ui.sellAssetCombo)
		self.late_inject_asset_box(tab.ui.buyAssetCombo)
		self.late_inject_asset_box(tab.ui.sellFeeAsset)
		self.late_inject_advanced_controls(
			editables=[
				tab.ui.sellAssetCombo,
				tab.ui.sellFeeAsset,
			],
			visibles=[
				tab.ui.sellFeeLabel,
				tab.ui.sellFeeAsset,
			]
		)
		config = self.iso.bts.config
		expire_seconds = config.get("order-expiration", 3600*24)
		expire_fok = bool(config.get("order-fillorkill", False))
		tab.ui.sellexpireEdit.setText(deltainterval(expire_seconds))
		tab.ui.fokCheckbox.setChecked(expire_fok)
		
		tab.openOrders(self.iso, account)
		
		return tab
	
	def addDashboardTab(self, account, tag):
		ui = self.ui
		
		tab = DashboardTab(ping_callback=self.refreshUi_ping)
		
		tab._tags = [
			account.name,
			account.id,
			"#account",
		]
		
		tab._title = _translate("MainWindow", "Account", None)
		tab._icon = None
		
		# Late comers!
		self.late_inject_advanced_controls(
			editables=[ ],
			visibles=[
				tab.ui.upgradeFeeLabel,
				tab.ui.upgradeFeeAsset,
				tab.ui.transferFeeLabel,
				tab.ui.transferFeeAsset,
				tab.ui.upgradeButton,
			]
		)
		self.late_inject_contact_box(
			tab.ui.transferToAccount
		)
		
		tab.openAccount(self.iso, account)
		tab.resync()
		
		return tab
	
	
	def quit_program(self):
		#self.app.quit()
		QtGui.QApplication.quit()
	
	def bootstrap_wallet(self, wipe=False):
		self.iso.bootstrap_wallet(wipe)
	
	def new_wallet_wizard(self):
		ww = WalletWizard(newOnly = True)
		ok, path, is_new, masterpwd = ww.run()
		if ok:
			app().reopen(path)
		return ok
	
	def new_wallet(self):
		path = DataDir.preflight()
		path, _ = QtGui.QFileDialog.getSaveFileName(self, 'New wallet file', path, "PyBitshares Wallet (*.bts *.sqlite)")
		
		if not path:
			return False
		
		password, ok = QtGui.QInputDialog.getText(
			None, 'Password',
			'Enter new master password:', QtGui.QLineEdit.Password)
		
		if not ok:
			return False
		
		if not password:
			password = 'default'
		
		from bitshares.wallet import Wallet
		
		try:
			##bitshares = iso.bts
			##bitshares.wallet.create(input)
			#store = BitsharesStorage(path)
			#self.iso = BitsharesIsolator()
			#self.iso.ping_callback = self.refreshUi_ping
			#wallet = Wallet(rpc=self.iso.bts.rpc, storage=store)
			#wallet.newWallet(input)
			
			#bitshares = iso.bts
			#bitshares.wallet.create(input)
			store = BitsharesStorageExtra(path, create=True)
			wallet = Wallet(rpc=None, storage=store)
			wallet.newWallet(password)
		
		except Exception as error:
			showexc(error)
			return False
		
		#self.iso.setWallet(wallet)
		#self.iso.setStorage(store)
		#self.bootstrap_wallet()
		
		#self.ui.statusLock.setToolTip(path)
		#self.refreshUi_wallet()
		
		#self.open_network_settings()
		#self.add_account()
		
		#self.open_wallet(path, autounlock=True)
		app().reopen(path)
		return True
	
	def setupUIfromConfig(self):
		#store = self.iso.store
		config =  self.iso.bts.config
		expand_users = bool( config.get('ui_showaccounts', False) )
		adv_mode = bool( config.get('ui_advancedmode', False) )
		expire_seconds = int( config.get('order-expiration', 3600*24) )
		expire_fok = bool( config.get('order-fillorkill', False) )
		
		for key,qact in self.config_triggers.items():
			show = bool( config.get(key, qact._default) )
			qact.setChecked(show)
			qact.triggered.emit(False)
		
		self.showAccountBar(expand_users)
		self.setAdvancedMode(adv_mode)
		
		self.ui.sellexpireEdit.setText(deltainterval(expire_seconds))
		self.ui.fokCheckbox.setChecked(expire_fok)
	
	def updateUIfromConfig(self):
		config =  self.iso.bts.config
		adv_mode = bool( config.get('ui_advancedmode', False) )
		self.setAdvancedMode(adv_mode)
	
	def _try_open_wallet(self, path, echo=False):
		try:
			ok = self.open_wallet(path, autounlock=False)
		except Exception as error:
			import traceback
			traceback.print_exc()
			if echo:
				showexc(error)
			return False
		return ok
	
	def auto_open_wallet(self):
		ok = False
		path = RecentWallets.last_wallet()
		if path:
			ok = self._try_open_wallet(path)
		if not ok:
			path = DataDir.preflight()
			ok = self._try_open_wallet(path)
		return ok
	
	
	def reopen_wallet(self):
		path = None
		path = DataDir.preflight()
		path, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open wallet file', path, "PyBitshares wallet (*.bts *.sqlite)")
		if not path:
			return False
		app().reopen(path)
	
	def open_wallet(self, path=None, autounlock=True):
		if not path:
			path = DataDir.preflight()
			path, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open wallet file', path, "PyBitshares wallet (*.bts *.sqlite)")
		if not path:
			return False
		
		if self.iso:
			self.close_wallet()
		
		from bitshares.wallet import Wallet
		store = BitsharesStorageExtra(path, create=False)
		self.iso = BitsharesIsolator(storage=store)
		self.iso.ping_callback = self.refreshUi_ping
		wallet = Wallet(
			blockchain_instance=self.iso.bts,
			rpc=self.iso.bts.rpc,
			storage=store)
		
		self.iso.setWallet(wallet)
		self.iso.setStorage(store)
		
		RecentWallets.push_wallet(path)
		
		self.ui.statusWallet.setText(path)
		
		self.setupUIfromConfig()
		self.refreshUi_wallet()
		
		n = self.loadAccounts()
		
		self.loadBlindAccounts()
		
		self.loadContacts()
		
		#print("Public keys in storage:")
		#from pprint import pprint
		#pprint(wallet.getPublicKeys())
		
		
		if autounlock:
			self.unlock_wallet()
		
		if n == 0: # Fresh wallet?
			self.open_network_settings()
			if askyesno("To function properly, a wallet file must have at least one BitShares account.\n\nAdd an account now?"):
				self.add_account()
		
		self.perhaps_autoconnect()
		
		return True
	
	def refreshUi_title(self):
		suffix = UNIX_NAME + " " + VERSION
		prefix = ""
		if self.activeAccount:
			prefix = self.activeAccount["name"] + " - "
		self.setWindowTitle(prefix + suffix)
	
	def refreshUi_console(self):
		from .work import Request
		bgtop = Request.top()
		
		#print("Background tasks: (%d)" % (len(bgtop)))
		
		table = self.ui.consoleList
		table.setRowCount(0)
		table.setColumnCount(3)
		
		j = -1
		for task in bgtop:
			j += 1
			
			(cancelled, desc, name, status) = task
			#print(("C" if cancelled else " ") +
			#	("%24s" % name) + " " + desc)
			
			table.insertRow(j)
			table.setItem(j, 0, QTableWidgetItem( ("cancelled" if cancelled else " ") ))
			table.setItem(j, 1, QTableWidgetItem( name ))
			table.setItem(j, 2, QTableWidgetItem( desc ))
		#print("")
	
	def refreshUi_ping(self):
		self.refreshUi_wallet()
	
	def refreshUi_wallet(self):
		wallet = self.iso.bts.wallet
		
		if wallet is None:
			self.ui.statusWallet.setText("")
			self.ui.statusLock.setText("")
			#self.ui.statusWallet.setIcon(None)#p(self.emptyPix)
			self.ui.statusLock.setIcon(self.emptyIcon)
			self.ui.actionClose_wallet.setEnabled(False)
			self.ui.actionUnlock_wallet.setEnabled(False)
			self.ui.actionLock_wallet.setEnabled(False)
			
			self.ui.accountsList.clear()
			return
		
		#self.ui.statusWallet.setPixmap(QtGui.QPixmap(":/icons/wallet_empty.png"))
		
		locked = wallet.locked()
		self.ui.statusLock.setToolTip("Locked" if locked else "Unlocked")
		if locked:
			#self.ui.statusLock.setPixmap(QtGui.QPixmap(":/icons/images/lock.png"))
			self.ui.statusLock.setIcon(qicon(":/icons/images/lock.png"))
		else:
			#self.ui.statusLock.setPixmap(QtGui.QPixmap(":/icons/images/unlock.png"))
			self.ui.statusLock.setIcon(qicon(":/icons/images/unlock.png"))
		
		self.ui.actionClose_wallet.setEnabled(True)
		self.ui.actionUnlock_wallet.setEnabled(True if locked else False)
		self.ui.actionLock_wallet.setEnabled(True if not locked else False)
		
		self.ui.actionUnlock_wallet_2.setEnabled(self.ui.actionUnlock_wallet.isEnabled())
		self.ui.actionLock_wallet_2.setEnabled(self.ui.actionLock_wallet.isEnabled())
		
		connected = not(self.iso.offline)
		
		if True:
			if self._connecting or (self.iso.bts.rpc and self.iso.bts.rpc.connecting):
				self.ui.statusText.setText("Connecting...")
				self.ui.statusNetwork.setToolTip("Connecting...")
				self.ui.statusNetwork.setIcon(qicon(":/icons/images/yellow.png"))
				connected = False
			elif connected:
				self.ui.statusText.setText("")
				self.ui.statusNetwork.setToolTip("Online")
				self.ui.statusNetwork.setIcon(qicon(":/icons/images/green.png"))
			else:
				self.ui.statusText.setText("")
				self.ui.statusNetwork.setToolTip("Offline")
				self.ui.statusNetwork.setIcon(qicon(":/icons/images/red.png"))
		
		self.ui.actionConnect.setEnabled(True if not connected else False)
		self.ui.actionDisconnect.setEnabled(True if connected else False)
		
		self.ui.actionConnect_2.setEnabled(self.ui.actionConnect.isEnabled())
		self.ui.actionDisconnect_2.setEnabled(self.ui.actionDisconnect.isEnabled())
		
		#self.ui.statusProxy.setText("")
		#self.ui.statusProxy.setPixmap(self.emptyPix)
		
		if connected:#self.iso.bts.rpc:
			proxy_type = self.iso.bts.rpc.proxy_type
			proxy_host = self.iso.bts.rpc.proxy_host
			proxy_port = int(self.iso.bts.rpc.proxy_port)
			if proxy_host:
				base_desc = proxy_type.upper() + "proxy"
				if (proxy_type == "socks5h" or proxy_type == "socks5") and\
					(proxy_host == "localhost" or proxy_host == "127.0.0.1") and\
					(proxy_port==9150 or proxy_port==9050):
					base_desc = "Onion Routing"
					#self.ui.statusProxy.setText("Proxy: TOR")
					#self.ui.statusProxy.setPixmap(QtGui.QPixmap(":/icons/images/onion.png"))
					#self.ui.statusNetwork.setText("Proxy: TOR")
					self.ui.statusNetwork.setIcon(qicon(":/icons/images/onion.png"))
				else:
					#self.ui.statusProxy.setText("Proxy: " + proxy_host)
					#self.ui.statusProxy.setPixmap(QtGui.QPixmap(":/icons/images/old/proxy32.png"))
					#self.ui.statusNetwork.setText("Proxy: " + proxy_host)
					self.ui.statusNetwork.setIcon(qicon(":/icons/images/onion.png"))
				if proxy_type != "socks5h":
					end_desc = " (DNS-leaking!)"
				else:
					end_desc = ""
				#self.ui.statusProxy.setToolTip("Online, " + base_desc + end_desc)
				self.ui.statusNetwork.setToolTip("Online, " + base_desc + end_desc)
		
		# Inform about background tasks:
		text = self.ui.statusText.text()
		if text == "":
			from .work import Request
			bgtop = Request.top()
			for task in bgtop:
				(cancelled, desc, c, s) = task
				if cancelled or not(desc):
					continue
				self.ui.statusText.setText("" + desc)
	
	def close_wallet(self):
		
		for name in list(self.open_accounts):
			self.closeAccount(name)
		
		if not(self.iso):
			return
		
		self.iso.disconnect()
		
		self.iso.setWallet(None)
		self.iso.setStorage(None)
		
		self.clear_account_names()
		self.clear_contact_names()
		self.clear_asset_names()
		
		self.refreshUi_wallet()
		
	
	def lock_wallet(self):
		wallet = self.iso.bts.wallet
		
		if wallet.locked():
			showerror("Already locked")
			self.refreshUi_wallet()
			return True
		
		try:
			wallet.lock()
		except Exception as e:
			showexc(e)
			return False
		
		self.refreshUi_wallet()
		return True
	
	def unlock_wallet(self, reason=None):
		wallet = self.iso.bts.wallet
		
		if not wallet.locked():
			showerror("Wallet is already unlocked")
			self.refreshUi_wallet()
			return True
		
		input, ok = QtGui.QInputDialog.getText(
			None, 'Password',
			(('To ' + reason + '\n\n') if reason else '') +
			'Enter wallet master password:', QtGui.QLineEdit.Password)
		
		if not ok:
			return False
		
		if not input:
			input = 'default'
		
		try:
			wallet.unlock(input)
		except Exception as e:
			showexc(e)
			return False
		
		#publickeys = wallet.getPublicKeys()
		#for pub in publickeys:
		#	priv = wallet.getPrivateKeyForPublicKey(pub)
		#	print("Private for ", pub, "=", priv)
		
		self.refreshUi_wallet()
		return True
	
	def clear_account_names(self):
		for box in self.account_boxes:
			box.clear()
		self.account_names = set()
	
	def clear_contact_names(self):
		for box in self.contact_boxes:
			box.clear()
		self.contact_names = set()
	
	def add_account_name(self, name):
		for box in self.account_boxes:
			box.addItem(name)
		self.account_names.add(name)
	
	def remove_account_name(self, name):
		for box in self.account_boxes:
			if isinstance(box, QtGui.QComboBox):
				item = box.findText(name, QtCore.Qt.MatchExactly)
				box.removeItem(item)
			else:
				item = box.findItems(name, QtCore.Qt.MatchExactly)[0]
				box.takeItem(box.row(item))
		self.account_names.remove(name)
	
	def add_contact_name(self, name):
		for box in self.contact_boxes:
			box.addItem(name)
			set_combo(box, "")
		self.contact_names.add(name)
	
	def remove_contact_name(self, name):
		for box in self.contact_boxes:
			if isinstance(box, QtGui.QComboBox):
				item = box.findText(name, QtCore.Qt.MatchExactly)
				box.removeItem(item)
			else:
				item = box.findItems(name, QtCore.Qt.MatchExactly)[0]
				box.takeItem(box.row(item))
		self.contact_names.remove(name)
	
	def late_inject_account_box(self, box):
		box.clear()
		for name in self.account_names:
			box.addItem(name)
		self.account_boxes.append(box)
	
	def late_inject_contact_box(self, box):
		box.clear()
		for name in self.contact_names:
			box.addItem(name)
		set_combo(box, "")
		self.contact_boxes.append(box)
	
	def clear_asset_names(self):
		for box in self.asset_boxes:
			box.clear()
		#self.asset_names = set()
	
	def add_asset_name(self, name):
		for box in self.asset_boxes:
			box.addItem(name)
		#self.asset_names.add(name)
	
	def late_inject_asset_box(self, box):
		self.asset_boxes.append(box)
	
	def evilDownloadHistory(self):
		ok = askyesno("Really delete all history?")
		if not ok:
			return
		store = self.iso.store.historyStorage
		
		store.wipe()
		self.massResync()
	
	def evilMergeAccounts(self):
		""" Do not call this, ever """
		if self.iso.offline:
			showerror("Must be online")
			return
		return self.mergeAccounts(wipe=True)
	
	def mergeAccounts(self, wipe=False, remove_unused=False):
		accountStore = self.iso.accountStorage
		if wipe:
			accountStore.wipe()
		
		cached = self.iso.getCachedAccounts()
		
		remote = self.iso.getRemoteAccounts()
		
		#from pprint import pprint
		#print("CACHED:")
		#pprint(cached)
		#print("REMOTE:")
		#pprint(remote)
		if remove_unused:
			for name in cached: # account exists locally
				if not(name in remote): # but not on blockchain
					self.iso.removeCachedAccount(name)
		
		for name in remote:
			if not(name in cached):
				
				account = self.iso.getAccount(name, cache=True)
				
				self.add_account_name(name)
		
	def add_account(self):
		try:
			with self.iso.unlockedWallet() as w:
				self._add_account()
		except WalletLocked:
			showerror("Can't add account to a locked wallet")
		except Exception as error:
			showexc(error)
	
	def _add_account(self):
		wallet = self.iso.bts.wallet
		
		win = AccountWizard(isolator=self.iso, registrars=self.account_names, active=self.activeAccount)
		
		if not win.exec_():
			return
		
		#pprint(win.field('keys'))
		#pprint(r)
		#print(win.ui.privkeysEdit.toPlainText())
		
		pks = win.collect_pks(quiet=False)
		
		for pk in pks:
			try:
				wallet.addPrivateKey(str(pk))
			except Exception as e:
				showerror(str(e), additional=pk)
		
		self.mergeAccounts()
		
		
	def _sweep_keys(self, account_name):
		wallet = self.iso.bts.wallet
		account = self.iso.getAccount(account_name)
		win = AccountWizard(
			isolator=self.iso,
			active=account,
			sweepMode=True
		)
		
		if not win.exec_():
			return 0
		
		#pprint(win.field('keys'))
		#pprint(r)
		#print(win.ui.privkeysEdit.toPlainText())
		
		pks = win.collect_pks(quiet=False)
		
		added = 0
		for pk in pks:
			try:
				wallet.addPrivateKey(str(pk))
				added += 1
			except Exception as e:
				import traceback
				traceback.print_exc()
				showerror(">>>>" + str(e), additional=pk)
		
		#if added == 0:
		#	# TODO: Remove old keys from wallet
		#	pass
		
		removed = self.iso.removeUselessKeys(account["id"])
		#self.mergeAccounts()
		return added

	def OTransfer(self, from_=None, to=None, amount=None, asset=None, memo=None):
		
		if from_ is True and self.activeAccount:
			set_combo(self.ui.transferFromAccount, self.activeAccount["name"])
		elif from_:
			if not(isinstance(from_, str)):
				from_ = from_["name"]
			set_combo(self.ui.transferFromAccount, from_)
		else:
			pass
		
		if to:
			if not(isinstance(to, str)):
				to = to["name"]
			set_combo(self.ui.transferToAccount, to)
		
		if asset:
			if not(isinstance(asset, str)):
				asset = asset["symbol"]
			set_combo(self.ui.transferAsset, asset, force=True)
		
		if amount:
			pass
		
		if not(memo is None):
			self.ui.transferMemo.setPlainText(memo)
		
		self.tagToFront("^transfer")
		#self.opToFront("!transfer")
	
	def FTransfer(self, account=None, to=None, amount=None, asset=None, memo=None):
		
		if account is True and self.activeAccount:
			account = self.activeAccount["name"]
		elif account:
			if not(isinstance(account, str)):
				account = account["name"]
		
		win = self.findTab(DashboardTab, account)
		
		#if to:
		#	if not(isinstance(to, str)):
		#		to = to["name"]
		#	set_combo(win.ui.transferToAccount, to)
		
		#if asset:
		#	if not(isinstance(asset, str)):
		#		asset = asset["symbol"]
		#	set_combo(self.ui.transferAsset, asset, force=True)
		
		#if amount:
		#	pass
		
		#if not(memo is None):
		#	win.ui.transferMemo.setPlainText(memo)
		
		if asset is None:
			asset = win._asset_name
		if asset is None:
			asset = "BTS"
		elif not(isinstance(asset, str)):
			asset = asset["symbol"]
		
		win.quick_transfer(asset, to, memo)
		
		self.showTab(win)
		#self.tagToFront("^transfer")
		#self.opToFront("!transfer")
	
	def OSell(self, account=None, sell_asset=None, sell_amount=None, buy_asset=None, buy_amount=None):
		
		if account is True and self.activeAccount:
			set_combo(self.ui.sellerBox, self.activeAccount["name"])
		elif account:
			if not(isinstance(account, str)):
				account = account["name"]
			set_combo(self.ui.sellerBox, account)
		else:
			pass
		
		if sell_asset:
			if not(isinstance(sell_asset, str)):
				sell_asset = sell_asset["symbol"]
			set_combo(self.ui.sellAssetCombo, sell_asset)
		
		if buy_asset:
			if not(isinstance(buy_asset, str)):
				buy_asset = buy_asset["symbol"]
			set_combo(self.ui.buyAssetCombo, buy_asset)
		
		if sell_amount:
			self.ui.sellAmountSpin.setValue(float(sell_amount))
		
		if buy_amount:
			self.ui.buyAmountSpin.setValue(float(buy_amount))
		
		self.tagToFront("^sell")
		#self.opToFront("!sell")
		
	def FSell(self, account=None, sell_asset=None, sell_amount=None, buy_asset=None, buy_amount=None):
		
		if account is True and self.activeAccount:
			account = self.activeAccount["name"]
		elif account:
			if not(isinstance(account, str)):
				account = account["name"]
		
		win = self.findTab(OrderTab, account)
		
		if sell_asset:
			if not(isinstance(sell_asset, str)):
				sell_asset = sell_asset["symbol"]
			set_combo(win.ui.sellAssetCombo, sell_asset)
		
		if buy_asset:
			if not(isinstance(buy_asset, str)):
				buy_asset = buy_asset["symbol"]
			set_combo(win.ui.buyAssetCombo, buy_asset)
		
		if sell_amount:
			win.ui.sellAmountSpin.setValue(float(sell_amount))
		
		if buy_amount:
			win.ui.buyAmountSpin.setValue(float(buy_amount))
		
		self.showTab(win)
		#self.tagToFront("orders")
		#self.opToFront("!sell")
		
	def OBlind(self, account=None, to=None, amount=None, asset=None):
		
		if account is True and self.activeAccount:
			set_combo(self.ui.blindFromAccount, self.activeAccount["name"])
		elif account:
			if not(isinstance(account, str)):
				account = account["name"]
			set_combo(self.ui.blindFromAccount, account)
		else:
			pass
		
		if asset:
			if not(isinstance(asset, str)):
				asset = asset["symbol"]
			set_combo(self.ui.blindFromAsset, asset)
		
		if amount:
			self.ui.blindFromAmount.setValue(float(amount))
		
		self.tagToFront("^blind")
		self.bt_page_to()