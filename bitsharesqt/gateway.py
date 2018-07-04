from PyQt4 import QtCore, QtGui

from rpcs.blocktradesus import BlockTradesUS
from rpcs.rudexorg import RuDexORG
from rpcs.winexpro import WinexPRO

from .bootstrap import KnownTraders

from .netloc import RemoteFetch
from .utils import *
import logging
log = logging.getLogger(__name__)

from pprint import pprint

import json
import time

class WindowWithGateway(QtCore.QObject):
	
	def init_gateway(self):
		
		self.cached_pairs = { }
		self.cached_coins= { }
		self.cached_wallets= { }
		
		self.rater = RemoteFetch()
		self.depositer = RemoteFetch()
		self.pairer = RemoteFetch()
		self.gwupdater = RemoteFetch()
		
		gb = self.ui.gatewayBox
		gb.addItem("select...", None)
		for name, url, refurl, factory in KnownTraders:
			gb.addItem(name, (url, refurl))
			self.cached_pairs[name] = [ ]
		gb.currentIndexChanged.connect(self.select_gateway)
		
		
		self.ui.inputCoinType.currentIndexChanged.connect(self.refresh_output_coin)
		#self.ui.inputCoinType.currentIndexChanged.connect(self.refresh_deposit_limit)
		
		#self.ui.inputCoinType.currentIndexChanged.connect(self.refresh_output_amount)
		#self.ui.outputCoinType.currentIndexChanged.connect(self.refresh_output_amount)
		#self.ui.outputCoinType.currentIndexChanged.connect(self.refresh_deposit_limit)
		
		self.ui.outputCoinType.currentIndexChanged.connect(self.refresh_address_selector)
		
		#val = QDoubleValidator(0, 100, 2, self)
		#self.ui.inputAmount.setValidator( val )
		
		self.ui.inputAmount.editingFinished.connect(self.refresh_output_amount)
		self.ui.inputAmount.returnPressed.connect(self.refresh_output_amount)
		
		#self.ui.outputAmount.editingFinished.connect(self.refresh_input_amount)
		#self.ui.outputAmount.returnPressed.connect(self.refresh_input_amount)
		
		self.ui.viewBridgeSetup.clicked.connect(self.gw_page_setup)
		self.ui.viewBridges.clicked.connect(self.gw_page_list)
		
		self.ui.swapButton.clicked.connect(self.swap_coin_types)
		
		self.ui.tradeButton.clicked.connect(self.begin_trade)
		
		self.ui.payButton.clicked.connect(self.activate_bridge)
		self.ui.payButton.hide()
		self.ui.externalpayButton.hide()
		
		self.ui.paymentList.itemClicked.connect(self.show_payment)
		self.ui.paymentList.itemActivated.connect(self.show_payment)
		
		self.gw_trans_timer = qtimer(60000, self.refresh_transactions)
		
		#stretch_tree(self.ui.bridgeDetails)
		self.ui.bridgeTransactions.setColumnCount(3)
		stretch_table(self.ui.bridgeTransactions, hidehoriz=True)
		self.ui.bridgeTransactions.itemSelectionChanged.connect(self.select_bridge_transaction)
		
		# hide scary initial stuff
		self.ui.gatewaySellAddress.hide()
		self.ui.gatewaySellAddressLabel.hide()
		self.ui.gatewaySellAccount.hide()
		self.ui.gatewaySellAccountLabel.hide()
		self.ui.gatewayBuyAddress.hide()
		self.ui.gatewayBuyAddressLabel.hide()
		self.ui.gatewayBuyAccount.hide()
		self.ui.gatewayBuyAccountLabel.hide()
		
		self.gw_page_list()
		

	
	def select_bridge_transaction(self):
		table = self.ui.bridgeTransactions
		
		items = table.selectedItems()
		if len(items) < 1:
			return
		
		item = items[0]
		tran = item.data(99)
		
		from pprint import pprint
		pprint(tran)
		self.ui.brtrnDate.setText(tran['inputFirstSeenTime'])
		self.ui.brtrnInTransaction.setText(tran['inputTransactionHash'])
		self.ui.brtrnOutTransaction.setText(tran['outputTransactionHash'])
		self.ui.brtrnId.setText(tran['transactionId'])
		
		#print( tran )
		#entry = store.getEntry(id)
		#config["node"] = str(item.text())
		#self.ui.nodeLabel.setText(str(config["node"]))
	
	
	
	def gw_page_setup(self):
		if not self.iso.bts.wallet:
			showerror("No wallet open")
			return False
		self.ui.gatewayStack.setCurrentIndex(0)
	def gw_page_list(self):
		self.ui.gatewayStack.setCurrentIndex(1)
	
	def _get_selected_bridge_entry(self):
		item = self.ui.paymentList.currentItem()
		if not item:
			return None
		#entry = item.data(99)
		internal_id = int(item.data(99))
		iso = self.iso
		store = iso.store.gatewayStorage;
		entry = store.getEntry(internal_id, 'id')
		return entry
	
	
	def activate_bridge(self):
		entry = self._get_selected_bridge_entry()
		if not entry:
			return
		
		receipt = json.loads(entry['receipt_json'])
		
		root = self.ui.bridgeDetails
		root.clear()
		
		
		if receipt and "inputCoinType" in receipt:
			self.FTransfer(
				account=True,
				to=receipt['inputAddress'],
				memo=receipt['inputMemo'],
				asset=receipt['inputCoinType'].upper())
	
	def _cache_coin(self, gwname, coindata):
		if not coindata:
			return
		
		if not gwname in self.cached_coins:
			self.cached_coins[gwname] = { }
		
		coinType = coindata["coinType"]
		if not coinType in self.cached_coins[gwname]:
			self.cached_coins[gwname][coinType] = coindata
	
	def _cache_wallet(self, gwname, walletdata):
		if not walletdata:
			return
		if not gwname in self.cached_wallets:
			self.cached_wallets[gwname] = { }
		
		walletType = walletdata["walletType"]
		if not walletType in self.cached_wallets[gwname]:
			self.cached_wallets[gwname][walletType] = walletdata
		
	
	def show_payment(self):
		#item = self.ui.paymentList.currentItem()
		#if not item:
		#	return
		#internal_id = int(item.data(99))
		iso = self.iso
		store = iso.store.gatewayStorage;
		
		entry = self._get_selected_bridge_entry()
		if not entry:
			return
		#entry = item.data(99)
		#entry = store.getEntry(internal_id, 'id')
		
		#pt = ""
		#pt += entry['receipt_json']
		#pt += "\n"
		#pt += entry['remote_json']
		#pt += "\n"
		#print(pt)
		
		root = self.ui.bridgeDetails
		root.clear()
		
		receipt = json.loads(entry['receipt_json'])
		transactions = json.loads(entry['remote_json']) if entry['remote_json'] else [ ]
		coindata = json.loads(entry['coindata_json'])
		walletdata = json.loads(entry['walletdata_json'])
		
		self._receipt = receipt
		
		gwname = entry['gateway']
		
		self._cache_coin(gwname, coindata)
		self._cache_wallet(gwname, walletdata)
		
		merge_in(root, receipt, "Invoice", "", iso=iso)
		merge_in(root, transactions, "Transactions", "", iso=iso)
		
		url = None
		gph = False
		
		if receipt and "inputCoinType" in receipt:
			self.ui.invoiceAddress.setText(receipt['inputAddress'])
			self.ui.invoiceMemo.setText(receipt['inputMemo'])
			if "gatewayName" in receipt:
				gwname = receipt["gatewayName"]
				
				coin = self.cached_coins[gwname][receipt["inputCoinType"]]
				wallet = self.cached_wallets[gwname][coin["walletType"]]
				
				#self.ui.qrView.setPixmap( None )
				if coin["walletType"] == 'bitshares2':
					gph = True
				if 'extraData' in wallet and wallet['extraData']:
					if 'uri' in wallet['extraData']:
						if 'address' in wallet['extraData']['uri']:
							template = wallet['extraData']['uri']['address']
							url = template.replace('${address}', receipt['inputAddress'])
				if not url and coin['coinType'] == 'btc':
					url = "bitcoin:${address}".replace('${address}', receipt['inputAddress'])
			
			self.ui.gwcalcInputLabel.setText(receipt["inputCoinType"].upper())
			self.ui.inputAmount.setEnabled(True)
		
			self.refresh_deposit_limit(receipt)
		if receipt and "outputCoinType" in receipt:
			self.ui.gwcalcOutputLabel.setText(receipt["outputCoinType"].upper())
			self.ui.outputAmount.setEnabled(True)
		if url:
			self.ui.qrView.setPixmap( make_qrcode_image(url).pixmap() )
			self.ui.qrView.show()
			self.ui.externalpayButton.show()
			self.ui.payButton.hide()
		elif gph:
			self.ui.qrView.setPixmap( QtGui.QPixmap(":/images/images/bitshares_logo.png" ) )
			self.ui.qrView.show()
			self.ui.externalpayButton.hide()
			self.ui.payButton.show()
		else:
			self.ui.qrView.hide()
			self.ui.payButton.hide()
			self.ui.externalpayButton.hide()
		
		self.ui.externalpayButton.hide() # TEMP
		
		print("IN DB:", transactions)
		self._redraw_transactions(transactions) # FROM DB
		self.refresh_transactions() # FROM GATEWAY
	
	def _redraw_transactions(self, transactions):
		
		table = self.ui.bridgeTransactions
		table.setRowCount(0)
		
		j = -1
		for tran in transactions:
			j += 1
			table.insertRow(j)
			
			ico = QtGui.QPixmap(":/icons/images/wait.png")
			if tran['transactionProcessingState'] == 'output_transaction_broadcast':
				ico = QtGui.QPixmap(":/icons/images/tick.png")
			if tran['transactionProcessingState'] in [
				'permanent_output_failure_never_confirmed', 'orphaned',
				'output_transaction_failed',
			]:
				ico = QtGui.QPixmap(":/icons/images/crossout.png")
			
			img = QtGui.QLabel("")
			img.setPixmap(ico)
			table.setCellWidget(j, 0, img)
			item0 = QtGui.QTableWidgetItem( str( tran['inputAmount'] ) )
			item0.setData(99, tran)
			table.setItem(j, 1, item0)
			#set_col(table, j, 1, tran['inputAmount'])
			set_col(table, j, 2, tran['outputAmount'])
		
		#self.ui.bridgeDetails.setPlainText(pt)
	
	
	def begin_trade(self):
		tr = self._collect_trade()
		if not tr['inputCoinType'] or not tr['outputCoinType']:
			return
		
		if not tr['outputAddress']:
			showerror("Please enter a withdrawal address")
			return
		
		trader = self._get_current_trader()
		gateway = self._get_current_trader_api(trader)
		
		(selling_from_graphene, buying_from_graphene,
			coindata, walletdata) = self._collect_trade_extra(tr)
		
		ioflag = (0
			| (0x01 if selling_from_graphene else 0)
			| (0x02 if buying_from_graphene else 0)
		)
		if selling_from_graphene and buying_from_graphene:
			showerror("BitShares-to-BitShares-via-Gateway trade is currently untested, proceed at your own risk")
		
		if not(selling_from_graphene) and not(buying_from_graphene):
			showerror("Neither end of this trade involves BitShares")
		
		if selling_from_graphene:
			account_name = tr['inputAddress']
		
		if buying_from_graphene:
			account_name = tr['outputAddress']
		
		if not coindata:
			coindata = self.__gwwd(gateway.coins(tr["inputCoinType"]))
			self._cache_coin(tr["gatewayName"], coindata)
		if not walletdata:
			walletdata = self.__gwwd(gateway.wallets(coindata["walletType"]))
			if "walletType" in walletdata:
				self._cache_wallet(tr["gatewayName"], walletdata)
			else:
				walletdata = None
		
		if not coindata or not walletdata:
			showerror("Unexpected malfunction")
			return
		
		try:
			receipt = gateway.initiate_trade(
				inputCoinType=tr['inputCoinType'],
				outputCoinType=tr['outputCoinType'],
				outputAddress=tr['outputAddress'],
				refundAddress=None,
				outputMemo=None)
		except Exception as error:
			showexc(error)
			return False
		
		receipt['gatewayName'] = tr['gatewayName']
		
		self.mergeExternalHistory_one(self.iso, account_name, ioflag, receipt, coindata, walletdata)
		
		self.gw_page_list()
	
	def __gwwd(self, data):
		if data["walletType"] == "btc":
			data["walletType"] = "bitcoin"
		return data
	
	def _collect_trade_extra(self, tr):
		selling_from_graphene = None
		buying_to_graphene = None
		inputCoin = None
		inputWallet = None
		name = tr['gatewayName']
		
		#from pprint import pprint
		#pprint(self.cached_wallets[name])
		
		if tr['inputCoinType']:
			try:
				inputCoin = self.cached_coins[name][tr['inputCoinType']]
				#inputWallet = self.cached_wallets[name][inputCoin['walletType']]
				if inputCoin['walletType'] == 'bitshares2':
					selling_from_graphene = True
				else:
					selling_from_graphene = False
			except:
				if "." in tr['inputCoinType']:
					selling_from_graphene = True
				else:
					selling_from_graphene = False
		
		if tr['outputCoinType']:
			try:
				outputCoin = self.cached_coins[name][tr['outputCoinType']]
				#outputWallet = self.cached_wallets[name][outputCoin['walletType']]
				if outputCoin['walletType'] == 'bitshares2':
					buying_to_graphene = True
				else:
					buying_to_graphene = False
			except:
				if "." in tr['outputCoinType']:
					buying_to_graphene = True
				else:
					buying_to_graphene = False
		
		return (
			selling_from_graphene,
			buying_to_graphene,
			inputCoin,
			inputWallet
		)
	
	def refresh_address_selector(self):
		name, _, _, _ = self._get_current_trader()
		tr = self._collect_trade();
		
		selling_from_graphene, buying_to_graphene, _, _ = self._collect_trade_extra(tr)
		
		if not(selling_from_graphene is None):
			if selling_from_graphene:
				self.ui.gatewaySellAccount.show()
				self.ui.gatewaySellAccountLabel.show()
				self.ui.gatewaySellAddress.hide()
				self.ui.gatewaySellAddressLabel.hide()
			else:
				self.ui.gatewaySellAddress.hide()
				self.ui.gatewaySellAddressLabel.hide()
				self.ui.gatewaySellAccount.hide()
				self.ui.gatewaySellAccountLabel.hide()
		
		if not(buying_to_graphene is None):
			if buying_to_graphene:
				self.ui.gatewayBuyAccount.show()
				self.ui.gatewayBuyAccountLabel.show()
				self.ui.gatewayBuyAddress.hide()
				self.ui.gatewayBuyAddressLabel.hide()
			else:
				self.ui.gatewayBuyAddress.show()
				self.ui.gatewayBuyAddressLabel.show()
				self.ui.gatewayBuyAccount.hide()
				self.ui.gatewayBuyAccountLabel.hide()
	
	def _collect_trade(self):
		def current_item(combo):
			i = combo.currentIndex()
			return combo.itemData(i)
		return {
			'inputCoinType': current_item(self.ui.inputCoinType),#.currentText(),
			'outputCoinType': current_item(self.ui.outputCoinType),#.currentText(),
			
			#'inputAmount': self.ui.inputAmount.text(),
			#'outputAmount': self.ui.outputAmount.text(),
			
			'gatewayName': self.ui.gatewayBox.currentText(),
			
			'inputAddress': self.ui.gatewaySellAccount.currentText() if self.ui.gatewaySellAccount.isVisible() else self.ui.gatewaySellAddress.text(),
			'outputAddress': self.ui.gatewayBuyAccount.currentText() if self.ui.gatewayBuyAccount.isVisible() else self.ui.gatewayBuyAddress.text(),
		}
		
	def _set_combo(self, combo, text):
		index = combo.findText(text, QtCore.Qt.MatchFixedString)
		if index >= 0:
			combo.setCurrentIndex(index)
	
	def swap_coin_types(self):
		(name, _, _, _) = self._get_current_trader()
		
		tr = self._collect_trade()
		
		trading_pairs = self.cached_pairs[name]
		
		for tp in trading_pairs:
			if (tp['inputCoinType'] == tr['outputCoinType'] and
				tp['outputCoinType'] == tr['inputCoinType']):
				
				#self.ui.inputAmount.setText("")
				#self.ui.outputAmount.setText(tr['inputAmount'])
				
				self._set_combo(self.ui.inputCoinType, tr['outputCoinType'].upper())
				self._set_combo(self.ui.outputCoinType, tr['inputCoinType'].upper())
	
	def _find_trader(self, name):
		for trader in KnownTraders:
			if trader[0] == name:
				return trader
		return None
	
	def _get_current_trader(self):
		return KnownTraders[self.ui.gatewayBox.currentIndex()];
	
	def _get_current_trader_api(self, trader=None):
		(name, url, refurl, factory) = trader or self._get_current_trader()
		proxy = self.iso.get_proxy_config()
		if '://localhost' in url: # Note: extremely unsecure test
			proxy = None
		poll = factory(endpoint=url, origin=refurl, proxyUrl=proxy)
		return poll
	
	def refresh_deposit_limit(self, tr=None):
		tr = tr or self._collect_trade()
		trader = self._find_trader(tr['gatewayName'])
		poll = self._get_current_trader_api(trader=trader)
		
		if not tr['outputCoinType'] or not tr['inputCoinType']:
			return
		
		self.ui.depositLimit.setText("")
		self.depositer.fetch(
			poll.deposit_limits,
					tr['inputCoinType'],
					tr['outputCoinType'],
			ready_callback=self.payment_deposit_limit,
			error_callback=self.payment_deposit_error,
			ping_callback=self.refreshUi_wallet,
			description="Refreshing deposit limits"
		)
		self.last_deposit_request_id = self.depositer.uid
		
		#try:
		#	res = poll.estimate_output_amount(
		#		input_amount,
		#		tr['inputCoinType'],
		#		tr['outputCoinType']
		#	)
		#except Exception as error:
		#	showexc(error)
		#	self.ui.outputAmount.setText("error")
		#	return
		#self.ui.outputAmount.setText(res['outputAmount'])
	def payment_deposit_error(self, request_id, error):
		print("Could not fetch deposit limit:", str(error))
		self.ui.depositLimit.setText("gateway error")
		self.refreshUi_wallet()
	
	def payment_deposit_limit(self, request_id, res):
		self.refreshUi_wallet()
		if self.last_deposit_request_id != request_id:
			return
		#tr = self._depositinfo
		self.ui.depositLimit.setText("%0.8f %s" % (float(res['depositLimit']), res["inputCoinType"].upper()))
	
	
	def refresh_output_amount(self):
		if not self.ui.inputAmount.text():
			return
		
		tr = self._receipt
		tr["inputAmount"] = self.ui.inputAmount.text()
		trader = self._find_trader(tr["gatewayName"])
		poll = self._get_current_trader_api(trader)
		
		if not tr['outputCoinType'] or not tr['inputCoinType']:
			return
		
		input_amount = float(tr['inputAmount'])
		if input_amount <= 0:
			return
		
		self.ui.outputAmount.blockSignals(True)
		self.ui.outputAmount.setText("")
		self.ui.outputAmount.blockSignals(False)
		
		self.rater.fetch(
			poll.estimate_output_amount,
					input_amount,
					tr['inputCoinType'],
					tr['outputCoinType'],
			ready_callback=self.estimated_output_amount,
			error_callback=self.estimated_output_error,
			ping_callback=self.refreshUi_wallet,
			description="Estimating output amount"
		)
		
	
	def estimated_output_error(self, request_id, error):
		print("Can not estimate outout:", str(error))
		self.ui.outputAmount.setText("error")
		
	def estimated_output_amount(self, request_id, res):
		tr = self._receipt # _collect_trade()
		
		print("COMP")
		from pprint import pprint
		pprint(tr)
		pprint(res)
		
		if (tr['inputCoinType'] == res['inputCoinType']
		and tr['outputCoinType'] == res['outputCoinType']
		and (float(tr['inputAmount']) == float(res['inputAmount']))):
			self.ui.outputAmount.blockSignals(True)
			self.ui.outputAmount.setText(res['outputAmount'])
			self.ui.outputAmount.blockSignals(False)
		#else:
		#	print("mismatch")
	
	def refresh_input_amount(self):
		if not self.ui.outputAmount.text():
			return
		
		tr = self._receipt
		tr["outputAmount"] = self.ui.outputAmount.text()
		trader = self._find_trader[tr["gatewayName"]]
		poll = self._get_current_trader_api(trader)
		
		if not tr['outputCoinType'] or not tr['inputCoinType']:
			return
		
		
		output_amount = float(tr['outputAmount'])
		if output_amount <= 0:
			return
		
		self.ui.inputAmount.blockSignals(True)
		self.ui.inputAmount.setText("")
		self.ui.inputAmount.blockSignals(False)
		
		self.rater.fetch(
			poll.estimate_input_amount,
					output_amount,
					tr['inputCoinType'],
					tr['outputCoinType'],
			ready_callback=self.estimated_input_amount,
			error_callback=self.estimated_input_error,
			ping_callback=self.refreshUi_wallet,
			description="Estimating input amount"
		)
	
	
	def refresh_transactions(self):
		entry = self._get_selected_bridge_entry()
		if not entry:
			return
		
		trader = self._find_trader(entry['gateway'])
		poll = self._get_current_trader_api(trader=trader)
		
		self.gwupdater.fetch(
			self.fetch_transactions,
				poll, entry,
			ready_callback=self.transactions_got,
			error_callback=self.transactions_error,
			ping_callback=self.refreshUi_wallet,
			description="Asking gateway about bridge transactions"
		)
	
	
	def fetch_transactions(self, gateway, entry):
		#trader = self._find_trader(entry['gateway'])
			
		receipt = json.loads(entry['receipt_json'])
		address = receipt['inputAddress']
		cointype = receipt['inputCoinType']
		memo = receipt['inputMemo']
		
		trades = gateway.transactions(address, cointype, memo)
		
		updates = [ ]
		updates.append((entry, trades))
		
		return (updates,)
	
	def transactions_got(self, request_id, args):
		(updates,) = args
		
		iso = self.iso
		store = iso.store.gatewayStorage
		
		for entry, trades in updates:
			store.updateEntry(entry['id'], "remote_json", json.dumps(trades))
		
		#self.show_payment()
		self._redraw_transactions(trades)
	
	
	def transactions_error(self, request_id, error):
		print("Could not get bridge transactions:", str(error))
	
	def select_gateway(self, j):
		gb = self.ui.gatewayBox
		
		if (gb.itemData(0) == None):
			gb.removeItem(0)
			j -= 1
		
		trader = KnownTraders[j]
		
		self.ui.inputAmount.setText('')
		self.ui.outputAmount.setText('')
		
		#self.ui.gatewayComment.setText("Updating coin lists on %s" % trader[0])
		
		self.pairer.fetch( self.grab_gateway_pairs, trader,
			ready_callback=self.grab_gateway_pairs_after,
			error_callback=self.grab_gateway_pairs_error,
			ping_callback=self.refreshUi_wallet,
			description="Updating coin lists on %s" % trader[0])
	
	def grab_gateway_pairs(self, trader):
		name, _, _, _ = trader
		gateway = self._get_current_trader_api(trader)
		
		self.ui.inputCoinType.clear()
		
		if not(name in self.cached_wallets) or True:
			wlts = gateway.wallets()
			for wallet in wlts:
				wallet = self.__gwwd(wallet)
				self._cache_wallet(name, wallet)
		
		if not(name in self.cached_coins) or True:
			cns = gateway.coins()
			for coin in cns:
				if not coin['walletType']:
					print("There is a coin without a wallet, skipping [%s]" % coin['coinType'])
					continue
				coin = self.__gwwd(coin)
				self._cache_coin(name, coin)
		
		trading_pairs = gateway.trading_pairs()
		self.cached_pairs[name] = trading_pairs
		
		return (name, )
	
	def grab_gateway_pairs_after(self, uid, args):
		(name, ) = args
		#name, _, _, _ = trader
		#gateway = self._get_current_trader_api(trader)
		
		storage = self.iso.store.gatewayStorage if self.iso.store else None
		
		for coin_name, coin in self.cached_coins[name].items():
			try:
				wallet = self.cached_wallets[name][coin['walletType']]
				storage.updateCoinData(name, coin['coinType'], json.dumps(coin), json.dumps(wallet))
			except:
				print(":(", coin_name, coin)
		
		
		self.ui.inputCoinType.clear()
		
		trading_pairs = self.cached_pairs[name]
		unique_left = set()
		
		for tp in trading_pairs:
			#{'inputCoinType': 'open.etp', 'outputCoinType': 'etp', 'rateFee': '0.'},
			unique_left.add(tp['inputCoinType'])
		
		ticon = qicon(":/icons/images/token.png")
		xicon = qicon(":/icons/images/coin.png")
		#self.cached_coins[name].items():
		for coin in sorted(unique_left):
			icon = xicon
			if coin in self.cached_coins[name]:
				cc = self.cached_coins[name][coin]
				if cc["walletType"] == "bitshares2":
					icon = ticon
			elif "." in coin:
				icon = ticon
			
			self.ui.inputCoinType.addItem(icon, coin.upper(), coin)
		
		#self.show_payment()
		
		#self.ui.gatewayComment.setText("")
		
		return True
	
	def grab_gateway_pairs_error(self, uid, error):
		showexc(error)
		#self.ui.gatewayComment.setText(str(error))
		
		return True
	
	def refresh_output_coin(self):
		trader = self._get_current_trader()
		name, _, _, _ = trader
		
		_ind = self.ui.inputCoinType.currentIndex()
		input_coin_type = self.ui.inputCoinType.itemData(_ind)#currentText()
		
		matching_right = set()
		trading_pairs = self.cached_pairs[name]
		for tp in trading_pairs:
			if tp['inputCoinType'] == input_coin_type:
				matching_right.add(tp['outputCoinType'])
		
		
		ticon = qicon(":/icons/images/token.png")
		xicon = qicon(":/icons/images/coin.png")
		self.ui.outputCoinType.clear()
		for coin in sorted(matching_right):
			icon = xicon
			if coin in self.cached_coins[name]:
				cc = self.cached_coins[name][coin]
				if cc["walletType"] == "bitshares2":
					icon = ticon
			elif "." in coin:
				icon = ticon
			self.ui.outputCoinType.addItem(icon, coin.upper(), coin)
	
	def openExternalHistory(self, iso, account):
		entries = iso.store.gatewayStorage.getAllEntries()#Entries(account.name);
		
		table = self.ui.paymentList
		
		#table.setRowCount(0)#;len(account.history())) #wtf
		#table.setColumnCount(2)
		
		table.clear()
		
		j = -1
		for h in entries:
			j += 1
			
			#table.insertRow(j);
			#table.setItem(j, 0, QTableWidgetItem( str(h[3] )))
			#table.setItem(j, 1, QTableWidgetItem( h[2] ))
			#pprint(h)
			item = QtGui.QListWidgetItem()
			item.setText( self._externalReceiptDescription(json.loads(h['receipt_json']) ))
			
			item.setData(99, h['id'] )
			table.addItem( item )
		
		
		#from netloc import RemoteFetch
		#f = RemoteFetch()
		#def on_ok(a, b):
		#	#print("OK!")
		#def on_err(a, b):
		#	#print("ERR!")
		#f.fetch( self.mergeExternalHistory_before, iso, account, ready_callback=on_ok, error_callback=on_err) 
	
	def queryExternalHistory(self, iso, account, external_address):
		pass
	
	def _externalReceiptDescription(self, receipt):
		return receipt["inputCoinType"].upper() + " -> " + receipt['gatewayName'] + " -> " + receipt["outputCoinType"].upper() + " -> " + receipt["outputAddress"]
	
	def mergeExternalHistory_one(self, iso, account_name, ioflag, receipt, coindata, walletdata):
		store = iso.store.gatewayStorage
		
		#if not trade_info:
		#	trade_info = [ ]
		
		id = store.add(
			account_name,
			gateway=receipt['gatewayName'],
			ioflag=ioflag,
			inputcointype=receipt['inputCoinType'],
			outputcointype=receipt['outputCoinType'],
			outputaddress=receipt['outputAddress'],
			receipt_json=json.dumps(receipt),
			coindata_json=json.dumps(coindata),
			walletdata_json=json.dumps(walletdata))
		
		table = self.ui.paymentList
		
		item = QtGui.QListWidgetItem()
		item.setText( self._externalReceiptDescription(receipt) )
		item.setData(99, id )
		table.addItem( item )
	