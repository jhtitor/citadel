from PyQt5 import QtCore, QtGui

from bitshares.amount import Amount
from bitshares.asset import Asset

from .netloc import RemoteFetch
from .utils import *

import json
from pprint import pprint

import logging
log = logging.getLogger(__name__)

class WindowWithMarkets(QtCore.QObject):

	def init_markets(self):
		self.ui.marketList.setColumnCount(5)
		stretch_table(self.ui.marketList, 1)
		qmenu(self.ui.marketList, self.show_market_submenu)
		self.ui.marketList.itemClicked.connect(self.display_market)

		self.ui.marketList.hide()

		self.ui.marketFilter.textEdited.connect(self._refilter_markets)
		self.ui.marketFilter.editingFinished.connect(self._refilter_markets)
		self.ui.marketFilter.returnPressed.connect(self._refilter_markets)
		
		self.ui.marketFilter.returnPressed.connect(self.find_market)
		self.ui.findMarketButton.clicked.connect(self.find_market)
		
		self.market_downloader = RemoteFetch()
		self.markets_downloader = RemoteFetch()
		
		self._markets = { }
		self._intr = [ ]
		
		#self.ui.findMarketButton.clicked.connect(self.find_asset)


	def display_market(self):
		j = table_selrow(self.ui.marketList)
		if j <= -1:
			return
		name = self.ui.marketList.item(j, 0).text()
		a, b = str.split(name, ":")
		pick = a
		
		current = self.ui.assetsymbolLine.text()
		if current == a:
			pick = b
		
		self.display_asset(pick)
	
	def _refilter_markets(self):
		self.refilter_markets()
		self.download_markets(self._intr)

	def refilter_markets(self):
		if not self.iso.store: # HACK -- closed already
			return
		
		iso = self.iso
		store = iso.store.assetStorage
		table = self.ui.marketList

		name = self.ui.marketFilter.text().upper()
		if not ":" in name:
			#table.setRowCount(0)
			self._showMarkets(False)
			return
		else:
			self._showMarkets(True)
		
		name_a, name_b = str.split(name, ":")

		if not name_a and not name_b:
			markets = [ m for (key,m) in self._markets.items() ]
			self._intr = [ ]
			self.place_markets(markets)
			return

		if not name_a or not name_b:
			table.setRowCount(0)
			return

		markets = [ ]
		self._intr = [ ]
		for (key, mtupl) in self._markets.items():
			if key.startswith(name):
				markets.append( mtupl )
				self._intr.append(mtupl[0])
		
		entries = store.getAssetsLike(name_b, limit=25)
		for graphene_json in entries:
			obj = json.loads(graphene_json)
			name = name_a+":"+obj["symbol"]
			if name in self._intr:
				continue
			markets.append( (name, { }, { }) )
			self._intr.append(name)
		
		self.place_markets(markets)
	
	def place_markets(self, markets):
		table = self.ui.marketList
		table.setRowCount(0)
		
		j = -1
		for (name, ticker, volume) in markets:
			j += 1
			table.insertRow(j)
			
			set_col(table, j, 0, str(name) )
			table.item(j, 0).setIcon(qicon(":/icons/images/market.png"))
			# 24h
			if not ticker:
				continue
			set_col(table, j, 1, "%0.2f" % float(ticker["percent_change"]) )
			set_col(table, j, 2, "%0.8f" % float(ticker["latest"]) + " " + str(volume["base"]))
			set_col(table, j, 3, "%0.2f" % float(volume["base_volume"]) + " " + str(volume["base"]) )
			set_col(table, j, 4, "%0.2f" % float(volume["quote_volume"]) + " " + str(volume["quote"]) )
		#if j <= -1:
		#if
		#	self._showMarkets(False)
		#else:
		#	self._showMarkets(True)
	
	def _showMarkets(self, on):
		sizePolicy = self.ui.assetList.sizePolicy() #QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
		#sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0 if on else 10)
		#sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
		self.ui.assetList.setSizePolicy(sizePolicy)
		
		#print("show markets:", on, "show assets:", not(on))
		self.ui.marketList.setVisible(on)
		self.ui.assetList.setVisible(not(on))
	
	def download_markets(self, markets=None, ignore_error=True):
		self.markets_downloader.fetch(
			self.iso.download_markets, markets,
			ready_callback=self.download_markets_after,
			error_callback=self._ignore_error if ignore_error else self._download_error,
			ping_callback=self.refreshUi_ping,
			description="Grabbing markets"
		)
	
	def _ignore_error(self, uid, error):
		pass
	def _download_error(self, uid, error):
		showexc(error)
	
	def download_markets_after(self, uid, args):
		#(markets, ) = args
		markets = args
		
		for m in markets:
			#print("one market:", m)
			self._markets[m[0]] = m
		
		self.refilter_markets()
	
	def download_market_after(self, uid, args):
		(name, ticker, volume) = args
		if not ticker:
			if iso.offline:
				showerror("You are offline")
			else:
				showerror("Market " + name + " not found")
			return
		self._markets[name] = (args)
		current = self.ui.marketFilter.text().upper()
		if current and name.startswith(current):
			self.refilter_markets()
	
	def find_market(self):
		pair = self.ui.marketFilter.text().upper()
		if not ":" in pair:
			return
		name_a, name_b = str.split(pair, ":")
		if not name_a or not name_b or (name_a==name_b):
			return
		self.market_downloader.fetch(
			self.iso.download_market,
			pair,
			ready_callback=self.download_market_after,
			error_callback=self._ignore_error,
			ping_callback=self.refreshUi_ping,
			description="Querying market " +pair,
		)
	
	def show_market_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Open Market", self._markets_open_market)
		qaction(self, menu, "Flip", self._markets_flip_market)
		menu.addSeparator()
		qmenu_exec(self.ui.marketList, menu, position)
	
	def _markets_open_market(self):
		table = self.ui.marketList
		j = table_selrow(table)
		if (j <= -1):
			return
		name = table.item(j, 0).text()
		(asset_name_a, asset_name_b) = str.split(name, ":")
		
		if asset_name_a == asset_name_b:
			return
		try:
			self.openMarket(asset_name_a, asset_name_b)
		except Exception as error:
			showexc(error)
			return
	
	
	def _markets_flip_market(self):
		table = self.ui.marketList
		j = table_selrow(table)
		if (j <= -1):
			return
		name = table.item(j, 0).text()
		self.iso._flipFaveMarket(name)
		self.download_markets()
	