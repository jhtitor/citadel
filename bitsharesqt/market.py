# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui
from .mainwindow import Ui_MainWindow

from uidef.market import Ui_MarketTab
_translate = QtCore.QCoreApplication.translate

from PyQt5.QtGui import QTableWidgetItem

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

import pyqtgraph as pg
import datetime

PG_BACKGROUND = 'w'
PG_FOREGROUND = 'k'
PG_LINEPEN    = pg.mkPen('g', width=3)
PG_CROSSHAIR  = 'y'

## Switch to using white background and black foreground
pg.setConfigOption('background', PG_BACKGROUND)
pg.setConfigOption('foreground', PG_FOREGROUND)

class MarketTab(QtGui.QWidget):

	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop("isolator", None)
		self.asset_a = kwargs.pop("asset_a", None)
		self.asset_b = kwargs.pop("asset_b", None)
		self._pairtag = self.asset_a["symbol"] + ":" + self.asset_b["symbol"]
		self.ping_callback = kwargs.pop("ping_callback", None)
		super(MarketTab, self).__init__(*args, **kwargs)
		self.ui = Ui_MarketTab()
		self.ui.setupUi(self)

		replaceAxis(self.ui.marketPlot, "bottom", TimeAxisItem(orientation='bottom'))
		replaceAxis(self.ui.marketPlot, "left", CoinAxisItem(precision=self.asset_b["precision"], orientation='left'))

		self.ui.marketPlot.setMenuEnabled(False)

		self.__vLine = pg.InfiniteLine(angle=90, movable=False, pen=PG_CROSSHAIR)
		self.__hLine = pg.InfiniteLine(angle=0, movable=False, pen=PG_CROSSHAIR)
		self.__textPrice = pg.TextItem('price')
		view = self.ui.marketPlot.getViewBox()
		view.addItem(self.__textPrice, ignoreBounds=True)
		view.addItem(self.__vLine, ignoreBounds=True)
		view.addItem(self.__hLine, ignoreBounds=True)
		view.setLimits(
#			yMin = 0, # price never goes below zero
			xMin = datetime.datetime(2015, 1, 1).timestamp(), # ~BTS started
			xMax = (datetime.datetime.now() + datetime.timedelta(weeks=52)).timestamp() # 1 year
		)

		self.start_time = None
		self.stop_time = None
		self.initfetch = 1
		self.ui.marketPlot.sigXRangeChanged.connect(self.updateRange)

		self.ui.marketPlot.scene().sigMouseMoved.connect(self.updateTooltip)
#,
#			axisItems={'bottom': TimeAxisItem(orientation='bottom')}

		self._index = 999

		self.ui.buyStack.setColumnCount(3)
		stretch_table(self.ui.buyStack, False, hidehoriz=True)
		self.ui.sellStack.setColumnCount(3)
		stretch_table(self.ui.sellStack, False, hidehoriz=True)

		self.subscribed = False
		self.updater = RemoteFetch(manager=self.iso.mainwin.Requests)

		self._frame_buy = {
			"group": self.ui.buyGroup,
			"mainLabel": self.ui.buyMainLabel,
			"mainAmt": self.ui.buyMainAmount,
			"altLabel": self.ui.buyAltLabel,
			"altAmt": self.ui.buyAltAmount,
			"price": self.ui.buyPrice,
			"account": self.ui.buyAccount,
			"expireEdit": self.ui.buyExpireEdit,
			"expireFOK": self.ui.buyFOK,
			"fee": self.ui.buyFeeAsset,
			"button": self.ui.buyButton,
			"_commit_inv": True,
			"table": self.ui.sellStack,
		}
		self._frame_sell = {
			"group": self.ui.sellGroup,
			"mainLabel": self.ui.sellMainLabel,
			"mainAmt": self.ui.sellMainAmount,
			"altLabel": self.ui.sellAltLabel,
			"altAmt": self.ui.sellAltAmount,
			"price": self.ui.sellPrice,
			"account": self.ui.sellAccount,
			"expireEdit": self.ui.sellExpireEdit,
			"expireFOK": self.ui.sellFOK,
			"fee": self.ui.sellFeeAsset,
			"button": self.ui.sellButton,
			"_commit_inv": False,
			"table": self.ui.buyStack,
		}
		self.setupFrame(self._frame_buy, self.asset_a, self.asset_b, title="Buy ")
		self.setupFrame(self._frame_sell, self.asset_a, self.asset_b, title="Sell ")
		
		#self.ui.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		#self.ui.table.customContextMenuRequested.connect(self.show_orders_submenu)
		
		self.ui.closeButton.clicked.connect(self.close_me)
		self.ui.swapButton.clicked.connect(self.swap_me)
		
	def close_me(self):
		app().mainwin.closeMarket(self._pairtag)
	
	def swap_me(self):
		try:
			app().mainwin.swapMarket(self._pairtag)
		except Exception as error:
			showexc(error)
	
	def close(self):
		# TODO: unsubscribe from market!!!
		pass
	
	def setupFrame(self, form, asset_a, asset_b, title="Trade "):
		form["group"].setTitle(title + asset_a["symbol"])
		form["mainLabel"].setText(asset_a["symbol"])
		form["altLabel"].setText(asset_b["symbol"])
		
		form["price"].valueChanged.connect(self.price_value_changed)
		form["price"].setSuffix(" " + asset_b["symbol"])
		form["price"].setDecimals(asset_b["precision"])
		form["price"].setMaximum(asset_b["options"]["max_supply"] * pow(10, asset_b["precision"]))
		form["mainAmt"].valueChanged.connect(self.main_amount_changed)
		form["mainAmt"].setDecimals(asset_a["precision"])
		form["mainAmt"].setMaximum(asset_a["options"]["max_supply"] * pow(10, asset_a["precision"]))
		form["altAmt"].valueChanged.connect(self.alt_amount_changed)
		form["altAmt"].setDecimals(asset_b["precision"])
		form["altAmt"].setMaximum(asset_b["options"]["max_supply"] * pow(10, asset_b["precision"]))
		
		form["table"].cellClicked.connect(self.cell_click)
		
		form["button"].clicked.connect(self.make_limit_order)

	def make_limit_order(self):
		form = self._frame_buy if self._frame_buy["button"] == self.sender() else self._frame_sell
		
		account_from = form["account"].currentText()
		sell_asset_name = self.asset_a["symbol"]
		sell_asset_amount = form["mainAmt"].value()
		buy_asset_name = self.asset_b["symbol"]
		buy_asset_amount = form["altAmt"].value()
		
		if form["_commit_inv"]:
			sell_asset_name = self.asset_b["symbol"]
			buy_asset_name = self.asset_a["symbol"]
			sell_asset_amount = form["altAmt"].value()
			buy_asset_amount = form["mainAmt"].value()
		
		expire_seconds = deltasec(form["expireEdit"].text())
		expire_fok = form["expireFOK"].isChecked()
		
		fee_asset = anyvalvis(form["fee"], None)#.currentText()
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
				isolator=self.iso)
			if buffer:
				app().mainwin._txAppend(*v)
			else:
				QTransactionBuilder._QExec(self.iso, v)
		except Exception as error:
			showexc(error)
			return False
		return True

	def _set_spin_value(self, elem, value):
		elem.blockSignals(True)
		elem.setValue(value)
		elem.blockSignals(False)

	def price_value_changed(self):
		form = self._frame_buy if self._frame_buy["price"] == self.sender() else self._frame_sell
		price = form["price"].value()
		amt_a = form["mainAmt"].value()
		amt_b = form["altAmt"].value()
		if amt_a == 0 and price != 0:
			amt_a = amt_b / price
			self._set_spin_value(form["mainAmt"], amt_a)
			return
		
		amt_b = amt_a * price
		self._set_spin_value(form["altAmt"], amt_b)

	def main_amount_changed(self):
		form = self._frame_buy if self._frame_buy["mainAmt"] == self.sender() else self._frame_sell
		price = form["price"].value()
		amt_a = form["mainAmt"].value()
		amt_b = form["altAmt"].value()
		if price == 0:
			if amt_a == 0:
				return
			price = amt_b / amt_a
			self._set_spin_value(form["price"], price)
			return
		
		amt_b = amt_a * price
		self._set_spin_value(form["altAmt"], amt_b)

	def alt_amount_changed(self):
		form = self._frame_buy if self._frame_buy["altAmt"] == self.sender() else self._frame_sell
		price = form["price"].value()
		amt_a = form["mainAmt"].value()
		amt_b = form["altAmt"].value()
		if price == 0:
			if amt_a == 0:
				return
			price = amt_b / amt_a
			#form["price"].setValue(price)
			self._set_spin_value(form["price"], price)
			return
		
		amt_a = amt_b / price
		self._set_spin_value(form["mainAmt"], amt_a)

	def cell_click(self, row, column):
		form = self._frame_buy if self._frame_buy["table"] == self.sender() else self._frame_sell
		valstr = form["table"].item(row, column).text().replace(",","")
		val = float( str.split(valstr, " ")[0] )
		if column == 0: # price
			form["price"].setValue(val)
		
		if column == 1: # asset_a
			form["mainAmt"].setValue(val)
		
		if column == 2: # asset_b
			form["altAmt"].setValue(val)

	def _refreshTitle(self):
		#self._title = _translate("MainWindow", "Market", None) + " " + self._pairtag
		self._title = self._pairtag
		return self._title

	def show_orders_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Cancel Order...", self.cancel_order)
		menu.exec_(self.ui.table.viewport().mapToGlobal(position))

	def cancel_order(self):
		table = self.ui.table
		indexes = table.selectionModel().selectedRows()
		if len(indexes) < 1:
			return
		index = indexes[0].row()
		
		order_id = table.item(index, 0).text()
		#b = table.item(index, 1).text()

		try:
			trx = QTransactionBuilder.QCancelOrder(
				self._account_name,
				order_id,
				#fee_asset=fee_asset,
				isolator=self.iso)
		except Exception as error:
			showexc(error)
	
	def desync(self):
		self.subscribed = False

	def resync(self):
		self.updater.fetch(
			self.mergeMarket_before, self.iso, (self.asset_a,self.asset_b), self._pairtag,
			self.start_time, self.stop_time,
			ready_callback=self.mergeMarket_after,
			ping_callback=self.ping_callback,
			description="Refreshing market " + self._pairtag)
	
	def mergeMarket_before(self, iso, pair, tag, start, stop):
		
		asset_a = pair[0]
		asset_b = pair[1]
		rpc = iso.bts.rpc
		if not self.subscribed:
			s_id = rpc.get_subscription_id()
			subs = rpc.subscribe_to_market(s_id, asset_a["id"], asset_b["id"])
			self._s_id = s_id
			self._tags.append("!" + str(s_id))
			self.subscribed = True
		
		from bitshares.market import Market
		self.market = Market(base=asset_b, quote=asset_a, blockchain_instance=iso.bts)
		
		orders = self.market.orderbook()
		if self.initfetch:
			trades = self.market.trades(limit=100, start=start, stop=stop)
		else:
			trades = iso.getMarketBuckets(self.market["base"], self.market["quote"], start=start, stop=stop)
		
		return (orders, trades,)
	
	def mergeMarket_after(self, request_id, args):
		(orders, trades,) = args
		
		self.fillTable(self.ui.buyStack, orders['bids'])
		self.fillTable(self.ui.sellStack, orders['asks'], True)
		self.plotChart(trades)
	
	def fillTable(self, table, orders, inv=False):
		color_a = COLOR_GREEN if inv else COLOR_RED
		color_b = COLOR_RED if inv else COLOR_GREEN
		table.setRowCount(0)
		
		j = -1
		for order in orders:
			j += 1
			
			table.insertRow(j)
			set_col(table, j, 0, price__repr(order, "base") )
			set_col(table, j, 1, str(order["quote"]), color=color_a, align="right" )
			set_col(table, j, 2, str(order["base"]), color=color_b, align="right" )
		
	
	def plotChart(self, trades):
		xs = [ ]
		ys = [ ]
		for trade in trades:
			dt = datetime.datetime.strptime(trade["date"], "%Y-%m-%dT%H:%M:%S")
			x = int(dt.timestamp()) #trade["sequence"]
			y = trade["price"]
			xs.append(x)
			ys.append(y)
		#print(xs, ys)
		#import numpy as np
		#x = np.random.normal(size=1000)
		#y = np.random.normal(size=1000)
		
		self.ui.marketPlot.blockSignals(True)
		self.ui.marketPlot.clear()
		self.ui.marketPlot.plot(xs, ys, pen=PG_LINEPEN)#, pen=None, symbol=None)
		obj = self.ui.marketPlot.getPlotItem()
		axis = obj.axes["bottom"]['item']
		axis._dayscale = False
		if len(xs) > 1: # Hack: adjust X-axis display
			if (xs[-1] - xs[0]) >= 3600 * 24: # >= 1 day
				axis._dayscale = True
		self.ui.marketPlot.blockSignals(False)
		
	def updateRange(self, view, rng):
		if self.initfetch > 0:
			self.initfetch -= 1
			return
		#price_low, price_high = rng[1] # (as integer)
		sec_start, sec_end = rng#[0]
		self.start_time = datetime.datetime.fromtimestamp(sec_start)
		self.stop_time = datetime.datetime.fromtimestamp(sec_end)
		self.resync()
	
	def updateTooltip(self, pos):
		data = self.ui.marketPlot.getPlotItem().listDataItems()
		if len(data) < 1: return
		points = data[0].curve
		act_pos = points.mapFromScene(pos)
		xs, ys = points.getData()

		x, j = snapTo(act_pos.x(), xs)
		if j < 0:
			self.__vLine.hide()
			self.__hLine.hide()
			self.__textPrice.hide()
			return
		y = ys[j]

		#print("SNAP:", j, x, y)
		self.__vLine.setPos(x)
		self.__hLine.setPos(y)
		self.__textPrice.setPos(x, y)

		price = "{price:.{precision}f}".format(price=y,precision=self.asset_b["precision"])
		self.__textPrice.setText(price)

		self.__vLine.show()
		self.__hLine.show()
		self.__textPrice.show()



class CoinAxisItem(pg.AxisItem):
	def __init__(self, *args, **kwargs):
		self._precision = kwargs.pop("precision", 5)
		super().__init__(*args, **kwargs)
	def tickStrings(self, values, scale, spacing):
		return ["{price:.{precision}f}".format(price=value,precision=self._precision) for value in values]
class TimeAxisItem(pg.AxisItem):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._dayscale = False
	def tickStrings(self, values, scale, spacing):
		fmt = "%H:%M"
		if self._dayscale:
			fmt = "%d.%I.%Y"
		return [int2dt(value).strftime(fmt) for value in values]
import datetime
def int2dt(ts, ts_mult=1e6):
	return (datetime.datetime.utcfromtimestamp(ts))#float(ts)/ts_mult))
def replaceAxis(widget, k, axis):
	obj = widget.getPlotItem()
	old = obj.axes[k]['item']
	pos = obj.axes[k]['pos']
	
	pos = {'top': (1,1), 'bottom': (3,1), 'left': (2,0), 'right': (2,2)}[k]
	unlinkFromView(old)
	
	obj.layout.removeItem(old)
	
	axis.linkToView(obj.vb)
	obj.axes[k] = {'item': axis, 'pos': pos}
	obj.layout.addItem(axis, *pos)
	axis.setZValue(-1000)
	axis.setFlag(axis.ItemNegativeZStacksBehindParent)
	
	axis.setGrid(64)

def unlinkFromView(axis):
	oldView = axis.linkedView()
	if oldView is None:
		return
	if axis.orientation in ['right', 'left']:
		oldView.sigYRangeChanged.disconnect(axis.linkedViewChanged)
	else:
		oldView.sigXRangeChanged.disconnect(axis.linkedViewChanged)
	oldView.sigResized.disconnect(axis.linkedViewChanged)

def price__repr(p, using="base"):
	return "{price:.{precision}f}".format(
		price=p["price"],
		precision=(p[using]["asset"]["precision"])
	)

def snapTo(v, vals):
	r = v
	l = 0
	j = -1
	for _v in vals:
		j += 1
		if v >= _v:
			r = _v
		else:
			diff1 = v - l
			diff2 = _v - v
			if diff2 < diff1:
				r = _v
			else:
				j -= 1
			break
		l = _v
	return r, j