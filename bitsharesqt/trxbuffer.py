from PyQt5 import QtCore, QtGui

from bitshares.transactionbuilder import TransactionBuilder
from bitsharesbase.operations import getOperationIdForClass
from bitsharesbase.operations import getOperationClassForId
from bitsharesbase.operations import getOperationNameForId

from .transactionbuilder import QTransactionBuilder

from .utils import *
import logging
log = logging.getLogger(__name__)

from pprint import pprint
import json
import time

class WindowWithTrxBuffer(QtCore.QObject):

	def init_trxbuffer(self):
		self.trxbuffer = None
		
		self.ui.txTable.setColumnCount(2)
		stretch_table(self.ui.txTable, hidehoriz=True)
		self.ui.txFrame.setVisible(False)
		
		self.ui.txCancelButton.clicked.connect(self.close_transactionbuffer)
		self.ui.txConfirmButton.clicked.connect(self.make_buffered_tx)
	
	def open_transactionbuffer(self):
		if not(self.ui.txFrame.isVisible()):
			showmessage("Collect several transactions into one. Press Apply when ready.")
			self.trxbuffer = TransactionBuilder(blockchain_instance=self.iso.bts)
		
		self._txRedraw()
		self.ui.txFrame.setVisible(True)
		
	def close_transactionbuffer(self):
		if len(self.trxbuffer.ops):
			ok = askyesno("Discard operations?")
			if not ok:
				return
		self._txClear()
		self.ui.txFrame.setVisible(False)
	
	def make_buffered_tx(self):
		try:
			self._txExec()
		except Exception as error:
			showexc(error)
	
	
	def _txAppend(self, op, sigs, redraw=True):
		tx = self.trxbuffer
		tx.appendOps(op)
		for (account, role) in sigs:
			if self.iso.bts.wallet.locked():
				tx.addSigningInformation(account, role, lazy=True)
			else:
				tx.appendSigner(account, role, lazy=True)
		if redraw:
			self._txRedraw()
	
	def _txClear(self):
		self.trxbuffer = None
		self.ui.txFrame.setVisible(False)
	
	def _txExec(self):
		self.trxbuffer["signatures"] = [ ]
		win = QTransactionBuilder(trxbuffer=self.trxbuffer,iso=self.iso)
		r = win.exec_()
		#print("QTransactionBuilder result:", r)
		if r:
			self._txClear()
			self.ui.txFrame.setVisible(False)
	
	def _txRedraw(self):
		root = self.ui.txTable
		trx = self.trxbuffer
		iso = self.iso
		
		root.setRowCount(0)
		
		j = -1
		for op in trx.ops:
			op_id = getOperationIdForClass(op.__class__.__name__)
			op_json = op.json()
			fake_obj = {
				'op': [op_id, op_json],
				'result': [0, True]
			}
			nextstatus = getOperationNameForId(op_id).upper()
			details = iso.historyDescription(fake_obj)
			description = details['long']
			
			j += 1
			root.insertRow(j)
			set_col(root, j, 0, nextstatus)
			set_col(root, j, 1, description)
		
		#table = self.ui.signatureTable
		#table.clear()
		#table.setRowCount(0)
		#self.ui.signedCheckbox.setChecked(False)
		#self.ui.broadcastButton.setEnabled(False)
		#j = -1
		#try:
		#	for sig in trx['missing_signatures']:
		#		j += 1
		#		table.insertRow(j)
		#		#pprint.pprint(sig)
		#		table.setItem(j, 0, QTableWidgetItem( "Missing: " + sig ))
		#except:
		#	pass
		#try:
		#	for sig in trx['signatures']:
		#		j += 1 
		#		table.insertRow(j)
		#		#pprint.pprint(sig)
		#		table.setItem(j, 0, QTableWidgetItem( sig ))
		#	if len(trx['signatures']):
		#		self.ui.signedCheckbox.setChecked(True)
		#		self.ui.broadcastButton.setEnabled(True)
		#except:
			#import traceback
			#traceback.print_exc()
		#	pass
	