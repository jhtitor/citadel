from PyQt5 import QtCore, QtGui

from bitshares.amount import Amount
from bitshares.asset import Asset

from .createasset import AssetWindow
from .netloc import RemoteFetch

from .utils import *
import logging
log = logging.getLogger(__name__)

import json
from pprint import pprint

class WindowWithAssets(QtCore.QObject):
	
	def init_assets(self):
		self.ui.assetList.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.ui.assetList.customContextMenuRequested.connect(self.show_asset_submenu)
		self.ui.assetList.itemSelectionChanged.connect(self.display_asset)
		self.ui.assetFrame.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.ui.assetFrame.customContextMenuRequested.connect(self.show_asset_submenu)
		
		stretch_table(self.ui.assetList)
		self.ui.assetFilter = self.ui.marketFilter# = self.uiAssetFilter
		#self.ui.downloadAssetsButton.clicked.connect(self.download_assets)
		self.ui.assetFilter.textEdited.connect(self.refilter_assets)
		self.ui.assetFilter.editingFinished.connect(self.refilter_assets)
		self.ui.assetFilter.returnPressed.connect(self.refilter_assets)
		
		self.ui.assetFilter.returnPressed.connect(self.find_asset)
		self.ui.findMarketButton.clicked.connect(self.find_asset)
		
		self.asset_downloader = RemoteFetch()
		self.assets_downloader = RemoteFetch()
		
	def display_asset(self, force_symbol=None, force_remote=False):
		if force_symbol:
			asset_name = force_symbol
		else:
			j = table_selrow(self.ui.assetList)
			if j <= -1:
				return
			asset_name = self.ui.assetList.item(j, 0).text()
		
		try:
			asset = self.iso.getAsset(asset_name, force_remote=force_remote)
		except Exception as ex:
			showexc(ex)
			return False
		
		self.ui.assetidLine.setText( asset['id'] )
		self.ui.assetsymbolLine.setText( asset['symbol'] )
		try:
			issuer = self.iso.softAccountName(asset['issuer'], remote=force_remote)
			self.ui.assetissuerLine.setText( issuer )
		except:
			self.ui.assetissuerLine.setText( asset['issuer'] )
		from pprint import pprint
		pprint(asset)
		self.ui.assetMaxSupply.setText( str(int(asset['options']['max_supply']) / pow(10, asset['precision'])) )
		self.ui.assetCurrentSupply.setText( str(int(asset['dynamic_asset_data'][ "current_supply"]) / pow(10, asset['precision'])) )
		self.ui.assetBlindSupply.setText( str(int(asset['dynamic_asset_data'][ "confidential_supply"]) / pow(10, asset['precision'])) )
		self.ui.assetFeePool.setText( str(int(asset['dynamic_asset_data']['fee_pool']) / pow(10, asset['precision'])) )
		self.ui.assetFeeRate.setText( str(int(asset['options']['core_exchange_rate']['base']['amount']) / pow(10, 5)) )
		#self.ui.assetFeeSupply.setText( str(int(asset['dynamic_asset_data']["accumulated_fees"] / pow(10, asset['precision']))) )
	
	def refilter_assets(self):
		iso = self.iso
		store = iso.store.assetStorage
		
		name = self.ui.assetFilter.text().upper()
		if ":" in name:
			a, b = str.split(name, ":")
			name = b
#			self.ui.assetList.setVisible(False)
#			self.ui.marketList.setVisible(True)
#		else:
#			self.ui.assetList.setVisible(True)
#			self.ui.marketList.setVisible(False)
		
		entries = [ ]
		if name:
			entries = store.getAssetsLike(name)
		elif self.activeAccount:
			entries = store.getByIssuer(self.activeAccount['id'])
		
		table = self.ui.assetList
		#table.setColumnCount(2)
		table.setRowCount(0)
		
		j = -1
		for graphene_json in entries:
			j += 1
			table.insertRow(j)
			
			obj = json.loads(graphene_json)
			#pprint(obj)
			desc = obj['options']['description']
			
			string = str(desc)
			try:
				parsed = json.loads(desc)
				if 'main' in parsed and parsed['main']:
					string = parsed['main']
				elif 'short_name' in parsed:
					string = parsed['short_name']
				else:
					string = ""
			except:
				# don't care
				#import traceback
				#traceback.print_exc()
				pass
			
			set_col(table, j, 0, obj['symbol'])
			set_col(table, j, 1, string)
			
			table.item(j, 0).setIcon( qicon(":/icons/images/token.png") )
	
	
	def evilDownloadAssets(self):
		if self.iso.offline:
			showerror("Must be online")
			return
		store = self.iso.store.assetStorage
		store.wipe()
		self.download_assets()
	
	def download_assets(self):
		self.assets_downloader.fetch(
			self.iso.download_assets,
			ready_callback=self.download_assets_after,
			error_callback=self._download_error,
			ping_callback=self.refreshUi_ping,
			description="Downloading asset definitions"
		)
	
	def _download_error(self, uid, error):
		showexc(error)
	
	def download_assets_after(self, uid, args):
		#(assets, ) = args
		pass
	
	def download_asset_after(self, uid, args):
		(asset) = args
		if not asset:
			if self.iso.offline:
				showerror("You are offline")
			else:
				showerror("Asset not found")
			return
		current = self.ui.assetFilter.text().upper()
		if current and current == asset["symbol"]:
			self.refilter_assets()
	
	def find_asset(self):
		symbol = self.ui.assetFilter.text().upper()
		if ":" in symbol:
			a, b = str.split(symbol, ":")
			symbol = b
		if not symbol:
			return
		
		self.asset_downloader.fetch(
			self.iso.download_asset,
			symbol,
			ready_callback=self.download_asset_after,
			error_callback=self._download_error,
			ping_callback=self.refreshUi_ping,
			description="Searching for asset " + symbol,
		)
	
	def show_asset_submenu(self, position):
		send = self.sender()
		menu = QtGui.QMenu()
		menu._list = True if send == self.ui.assetList else False
		qaction(self, menu, "Buy...", self._buy_asset)
		qaction(self, menu, "Sell...", self._sell_asset)
		qaction(self, menu, "Open Market", self._openmarket_asset)
		menu.addSeparator()
		qaction(self, menu, "Edit Asset...", self._edit_asset)
		qaction(self, menu, "Issue Asset...", self._issue_asset)
		#qaction(self, menu, "Reserve Asset...", self._reserve_asset)
		qaction(self, menu, "Fund Fee Pool...", self._fundfee_asset)
		if not(menu._list):
			menu.exec_(send.mapToGlobal(position))
		else:
			menu.exec_(send.viewport().mapToGlobal(position))
	
	def _submenu_asset(self):
		top = self.sender().parent()
		if isinstance(top, QtGui.QMenu):
			print("Yes is asset!", self.ui.assetsymbolLine.text())
			return self.ui.assetsymbolLine.text()
		j = table_selrow(self.ui.assetList)
		if j < 0:
			return None
		asset_name = self.ui.assetList.item(j, 0).text()
		return asset_name

	def _buy_asset(self):
		asset_name = self._submenu_asset()
		if not asset_name:
			return
		self.FSell(account=True, buy_asset=asset_name)
	
	def _sell_asset(self):
		asset_name = self._submenu_asset()
		if not asset_name:
			return
		self.FSell(account=True, sell_asset=asset_name)
	
	def _openmarket_asset(self):
		asset_name = self._submenu_asset()
		asset = self.iso.getAsset(asset_name)
		desc = asset["options"]["description"]
		market = None
		try:
			market = json.loads(desc)["market"]
		except:
			pass
		if not(market):
			market = "BTS"
		app().mainwin.openMarket(asset_name, market)
	
	def _edit_asset(self):
		asset_name = self._submenu_asset()
		if not asset_name:
			return
		asset = self.iso.getAsset(asset_name)
		win = AssetWindow(isolator=self.iso, mode="edit",
			asset=asset,
			accounts=self.account_names,
			account=self.activeAccount)
		win.exec_()
	
	def _edit_bitasset(self):
		asset_name = self._submenu_asset()
		if not asset_name:
			return
		asset = self.iso.getAsset(asset_name)
		win = AssetWindow(isolator=self.iso, mode="bitasset",
			asset=asset,
			accounts=self.account_names,
			account=self.activeAccount)
		win.exec_()
	
	def _issue_asset(self):
		asset_name = self._submenu_asset()
		if not asset_name:
			return
		asset = self.iso.getAsset(asset_name)
		win = AssetWindow(isolator=self.iso, mode="issue",
			asset=asset,
			accounts=self.account_names,
			account=self.activeAccount)
		win.exec_()
	
	def _reserve_asset(self):
		asset_name = self._submenu_asset()
		if not asset_name:
			return
		asset = self.iso.getAsset(asset_name)
		win = AssetWindow(isolator=self.iso, mode="reserve",
			asset=asset,
			accounts=self.account_names,
			account=self.activeAccount)
		win.exec_()
	
	def _fundfee_asset(self):
		asset_name = self._submenu_asset()
		if not asset_name:
			return
		asset = self.iso.getAsset(asset_name)
		win = AssetWindow(isolator=self.iso, mode="fund",
			asset=asset,
			accounts=self.account_names,
			account=self.activeAccount)
		win.exec_()
	