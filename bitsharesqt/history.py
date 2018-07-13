# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui, QtWidgets

from PyQt5.QtWidgets import QTableWidgetItem

from .netloc import RemoteFetch
from .utils import *
import json

from .memowindow import MemoWindow
from .transactionbuilder import QTransactionBuilder

from bitsharesbase.signedtransactions import Signed_Transaction

import logging
log = logging.getLogger(__name__)

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class Ui_HistoryTab(object):

	def setupUi(self, tab):

		self.tab = tab
		#tab = QtGui.QWidget()
		#tab.setObjectName(_fromUtf8("tab_3"))

		self.verticalLayout = QtGui.QVBoxLayout(tab)
		self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))

		self.table = QtGui.QTableWidget(tab)
		self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
		self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
		self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		self.table.setShowGrid(False)
		self.table.setCornerButtonEnabled(False)
		self.table.setRowCount(0)
		self.table.setColumnCount(4)
		self.table.setObjectName(_fromUtf8("tableWidget_3"))
		self.table.horizontalHeader().setVisible(False)
		self.table.horizontalHeader().setDefaultSectionSize(294)
		self.table.verticalHeader().setVisible(False)
		self.verticalLayout.addWidget(self.table)
		
		#font = QtGui.QFont()
		#font.setFamily(_fromUtf8("Monospace"))
		#font.setPointSize(10)
		#self.table.setFont(font)
		
		self.table.setStyleSheet(_fromUtf8("QTableWidget {\n"
			"    font-family: monospace;\n"
			"}\n"
			"QTableWidget::item { padding-right: 20px; }\n"
			"\n"
		""))
		
		header = self.table.horizontalHeader()
		header.setResizeMode(0, QtGui.QHeaderView.ResizeToContents)
		header.setResizeMode(1, QtGui.QHeaderView.Stretch)
		header.setResizeMode(2, QtGui.QHeaderView.ResizeToContents)
		header.setResizeMode(3, QtGui.QHeaderView.ResizeToContents)
		
		#table.verticalHeader().hide()
		#table.horizontalHeader().hide()
		
		#self.tabWidget.addTab(self.tab_3, _fromUtf8(""))
		
		#self.retranslateUi(MainWindow)
		#self.tabWidget.setCurrentIndex(5)
		#QtCore.QMetaObject.connectSlotsByName(MainWindow)
	
	#def retranslateUi(self, MainWindow):
	#	pass

class HistoryTab(QtWidgets.QWidget):
	
	def __init__(self, *args, **kwargs):
		self.ping_callback = kwargs.pop("ping_callback", None)
		super(HistoryTab, self).__init__(*args, **kwargs)
		self.ui = Ui_HistoryTab()
		self.ui.setupUi(self)
		
		self._index = 1
		
		self.subscribed = False
		self.updater = RemoteFetch()
		self.refreshing = False
		
		self.ui.table.cellDoubleClicked.connect(self.history_superclick)
		
		qmenu(self.ui.table, self.show_submenu)
	
	def show_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Details", self.history_click)
		qaction(self, menu, "Read Memo", self.history_memo)
		qaction(self, menu, "Show Blind Receipts", self.history_receipts)
		qaction(self, menu, "View on Block Explorer...", self.history_viewexplorer)
		menu.addSeparator()
		qaction(self, menu, "Copy Block Number", self.history_copy_blocknum)
		qaction(self, menu, "Copy Transaction Hash", self.history_copy_trxid)
		menu.addSeparator()
		qaction(self, menu, "Export History...", self.export_history)
		qmenu_exec(self.ui.table, menu, position)
	
	def export_history(self):
		account = self._last_account
		iso = self._last_iso
		entries = iso.store.historyStorage.getEntries(account.name)
		
		path = account.name + ".csv"
		path, _ = QtGui.QFileDialog.getSaveFileName(self, 'Export account history', path, "CSV File (*.csv)")
		if not path:
			return False
		
		with open(path, "w") as f:
			s = "Date, Operation, Income, Expense\n"
			f.write(s)
			for h in entries:
				if not '_details' in h:
					h['_details'] = json.loads(h['details']) if h['details'] else {
						"plus": "", "minus": "",
					}
				s = "%s, %s, %s, %s\n" % (
					str(h["date"]),
					h["description"],
					h["_details"]["plus"],
					h["_details"]["minus"]
				)
				f.write(s)
		return True
	
	def history_memo(self):
		j = table_selrow(self.ui.table)
		if j < 0:
			return
		h = self.ui.table.item(j, 0).data(99)
		#if h["memo"] == -1:
		#	return False
		info = json.loads(h['operation'])
		op_id, op = info["op"]
		if not op or not(op_id == 0):
			return
		if not("memo" in op):
			return
		
		iso = self._last_iso
		
		try:
			account_from = iso.getAccount(op["from"])
		except:
			account_from = None
		try:
			account_to = iso.getAccount(op["to"])
		except:
			account_to = None
		
		with iso.unlockedWallet() as w:
			MemoWindow.QReadMemo(iso, op['memo'],
				source_account=account_from,
				target_account=account_to)
#		try:
#			data = op['memo']
#			clear = iso.getMemo(None, None, data=data)
#		except Exception as error:
#			showexc(error)
	
	def history_receipts(self):
		j = table_selrow(self.ui.table)
		if j < 0:
			return
		h = self.ui.table.item(j, 0).data(99)
		#if h["memo"] == -1:
		#	return False
		info = json.loads(h['operation'])
		#print(info)
		op_id, op = info["op"]
		if not op or not(op_id == 39 or op_id == 40):
			return
		
		iso = self._last_iso
		(n, text, txt2) = iso.matchBlindOutputs(op["outputs"], h["description"])
		
		if n == 0:
			showerror("No receipts found")
			return
		
		showmsg("Found %d blind receipt(s)" % n, additional=txt2, details=text)
	
	def history_viewexplorer(self):
		j = table_selrow(self.ui.table)
		if j < 0:
			return
		h = self.ui.table.item(j, 0).data(99)
		
		url = "http://bitshares-explorer.io/#/blocks/${block}"
		url = "http://cryptofresh.com/tx/${tx}"
		url = url.replace("${tx}", h['trxid'])
		url = url.replace("${block}", str(h['block_num']))
		import webbrowser
		webbrowser.open(url)
	
	def history_copy_blocknum(self):
		j = table_selrow(self.ui.table)
		if j < 0:
			return
		h = self.ui.table.item(j, 0).data(99)
		
		qclip(str(h['block_num']))
	
	def history_copy_trxid(self):
		j = table_selrow(self.ui.table)
		if j < 0:
			return
		h = self.ui.table.item(j, 0).data(99)
		
		if not h['trxid']:
			showerror("Transaction has no ID :(")
			return
		
		qclip(h['trxid'])
	
	def history_click(self):
		j = table_selrow(self.ui.table)
		if j < 0:
			return
		self.history_superclick(j, 0)
	
	def history_superclick(self, row, column):
		h = self.ui.table.item(row, 0).data(99)
		op_id = h['op_index']
		#op_id = self.ui.table.item(row, 0).text()
		iso = self._last_iso
		entry = h# iso.store.historyStorage.getEntry(op_id, self._account_name)
		#print("predata", entry["operation"])
		data = json.loads(entry["operation"])
		op = data['op'][1]
		
		if entry["trxfull"]:
			ftx = json.loads(entry["trxfull"])
			hl = int(entry["op_in_trx"])
			QTransactionBuilder.QViewTransaction(ftx, hl, isolator=self._last_iso)
			return
		
		if 'memo' in op:
			MemoWindow.QReadMemo(iso, op['memo'])
		#from pprint import pprint
		#pprint(entry)
		#showerror(str(op_id))
		#showerror(str(entry))
		#showerror(str(data))
	
	def close(self):
		self.updater.cancel()
	
	def openHistory(self, iso, account):
		self._last_iso = iso
		self._last_account = account
		entries = iso.store.historyStorage.getEntries(account.name)
		
		self._account_name = account.name
		self._account_id = account.id
		#table.setRowCount(0)#len(account.history())) #wtf
		#table.setColumnCount(2)
		
		self.place_entries(entries)
		self.resync()
	
	def place_entries(self, entries):
		table = self.ui.table
		
		j = -1
		for h in entries:
			j += 1
			
			if not '_details' in h:
				h['_details'] = json.loads(h['details']) if h['details'] else {
					"short": h['description'],
					"plus": "", "minus": "",
					"icon": None
				}
				# TODO: remove this block
				if not('icon' in h['_details']): #
					h['_details']['icon'] = None#
			if not('_icon' in h):
				h['_icon'] = ":/op/images/op/"+h['_details']['icon']+".png" if h['_details']['icon'] else None
			description = h["_details"]["short"] or h['description']
			
			table.insertRow(j)
			
			item = QTableWidgetItem( str(h["date"]) )
			item.setData(99, h)
			table.setItem(j, 0, item)
			icon = qicon(h["_icon"])
			item.setIcon(icon)
			
			set_col(table, j, 1, description)
			set_col(table, j, 2, h["_details"]["plus"], color=COLOR_GREEN, align="right")
			set_col(table, j, 3, h["_details"]["minus"], color=COLOR_RED, align="right")
		
			if h["memo"] > 0:
				icon = qicon(":/icons/images/memo.png")
				table.item(j, 1).setIcon(icon)
	
	
	def desync(self):
		self.subscribed = False
	
	def resync(self):
		if not self.refreshing:
			self.mergeHistory_async(self._last_iso, self._last_account)
	
	# blocking version
	def mergeHistory(self, iso, account):
		raise Exception("Don't call me")
		mergeHistory_after(0, mergeHistory_before(iso, account))
	
	#non-blocking version
	def mergeHistory_async(self, iso, account, overpower=False):
		if self.refreshing: # already busy
			if overpower:
				self.updater.cancel()
			else:
				return
		self.refreshing = True
		self.updater.fetch(
			self.mergeHistory_before, iso, account,
			ready_callback = self.mergeHistory_after,
			error_callback = self.mergeHistory_abort,
			ping_callback = self.ping_callback,
			description="Synchronizing history"
		)
	
	def mergeHistory_before(self, iso, account):
		self.refreshing = True
		
		#iso._wait_online(timeout=3) # will raise exception
		#if not(iso.is_connected()):
		#	raise Exception
		
		# subscribe
		rpc = iso.bts.rpc
		if not self.subscribed:
			rpc.get_full_accounts([account.name], True)
			self.subscribed = True
		
		# fetch history
		last_op_index = iso.store.historyStorage.getLastOperation(account.name)
		log.debug("Last OP INDEX for %s = %s" % (account.name, last_op_index))
		
		# recreate account object
		#from bitshares.account import Account
		#account = Account(account.name, blockchain_instance=iso.bts)
		
		# load from the net
		history = list(account.history())
		
		# load full tx from net + generate description
		t = 0
		for h in history:
			if (h['id'] == last_op_index):
				break
			t += 1
			#print("Get full tx for",
			#	int(h['block_num']), int(h['trx_in_block']),
			#	int(h['op_in_trx']), int(h["virtual_op"]))
			try:
				ftx = iso.bts.rpc.get_transaction(int(h['block_num']), int(h['trx_in_block']))
			except Exception as error:
				#print(str(error))
				ftx = { }
			#print(ftx)
			h['_fulltx_dict'] = ftx
			h['_fulltx_obj' ] = Signed_Transaction(**ftx) if ftx else None
			h['_fulltx'] = json.dumps(ftx)
			
			h['_memo'] = 0
			import bitshares.exceptions
			try:
				if h['op'][0] == 0:
					h['_memo'] = -1
					if "memo" in h['op'][1]:
						data = h['op'][1]['memo']
						clear = iso.getMemo(None, None, data=data)
						if len(clear["message"]) > 0:
							h['_memo'] = 1
			except bitshares.exceptions.WalletLocked:
				h['_memo'] = 1
			except Exception as e:
				#import traceback
				#print(h['op'][1], "failed to metch memo-data")
				#traceback.print_exc()
				pass
			
			#print("Get description for", h)
			h['_details'] = iso.historyDescription(h, account)
			h['_icon'] = ":/op/images/op/"+h['_details']['icon']+".png"
			h['description'] = h['_details'].pop('long')
			h['details'] = json.dumps(h['_details'])
		
		history = history[0:t]
		return (history, account.name, iso)
	
	def mergeHistory_after(self, request_id, args):
		(history, account_name, iso) = args
		
		#last_op_index = iso.store.historyStorage.getLastOperation(account.name)
		last_op_index = "disabled"
		
		added = [ ]
		
		#from pprint import pprint
		#print("New entries:", len(history))
		for h in history:#account.history():
			
			#pprint(h)
			#print("NEW OP INDEX:", h['id'])
			
			op_index = h['id']
			if (op_index == last_op_index):
				break
			
#			if not 'description' in h:
#				description = "...?"
#			else:
			description = h['description'] #iso.historyDescription(h)
			
			#mem_tx = Signed_transaction(
			
			trxid = '...' # TODO: get txid from tx full
			short = {
				'op': h['op'],
				'result': h['result']
			}
			memo = 0
			if '_memo' in h:
				memo = int(h['_memo'])
			
			exp_date = None
			ftx = h['_fulltx_dict']
			if ftx:
				signed = h['_fulltx_obj']
				try:
					trxid = signed.id # it's a property
				except:
					trxid = ''
				if 'expiration' in ftx and ftx['expiration']:
					exp_date = ftx['expiration']
					if exp_date[10:11] == 'T': # prettify
						exp_date = exp_date.replace('T', ' ')
			try:
				iso.store.historyStorage.add(
					account_name, description,
					op_index, json.dumps(short), memo,
					int(h['block_num']), int(h['trx_in_block']), int(h['op_in_trx']),
					int(h['virtual_op']),
					trxid, json.dumps(ftx), h['details']
				)
				if exp_date:
					iso.store.historyStorage.updateDate(op_index, exp_date)
				h = iso.store.historyStorage.getEntry(op_index, account_name)
			except:
				import traceback
				traceback.print_exc()
				continue
			
			added.append(h)
		
		log.debug("COLLECTED %d pieces of history, ADDING TO UI" % (len(added)))
		self.place_entries(added)
		self.refreshing = False
	
	def mergeHistory_abort(self, uid, error):
		log.debug("Failed to merge history: %s" % (str(error)))
		self.refreshing = False
	