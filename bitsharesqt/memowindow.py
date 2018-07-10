from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.memowindow import Ui_MemoWindow

from .utils import *
import json

import logging
log = logging.getLogger(__name__)

class MemoWindow(QtWidgets.QDialog):

	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('isolator', None)
		super(MemoWindow, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_MemoWindow()
		
		ui.setupUi(self)
		
		self.ui.closeButton.clicked.connect(self.reject)
		
		self.ui.readButton.clicked.connect(self.read_memo)
		self.ui.signButton.clicked.connect(self.sign_memo)
		
	
	@classmethod
	def QReadMemo(self, iso, memo_data, source_account=None, target_account=None):
		win = MemoWindow(isolator=iso)
		
		win.set_from_data(memo_data)
		win.read_memo()#source_account, target_account)
		win.set_readonly()
		
		return win.exec_()
	
	def set_from_data(self, memo_data):
		#source_name = memo_data['from']
		#taget_name = memo_data['to']
		#self.ui.
		#cipher_message = self.ui.cipherMessage.toPlainText()
		#data = json.loads(cipher_message)
		self.ui.cipherMessage.setPlainText(json.dumps(memo_data))
	
	def set_readonly(self):
		
		self.ui.accountFrom.setEnabled(False)
		self.ui.accountTo.setEnabled(False)
		self.ui.clearMessage.setReadOnly(True)
		self.ui.cipherMessage.setReadOnly(True)
		
		self.ui.signButton.setEnabled(False)
		self.ui.readButton.setEnabled(False)
	
	def sign_memo(self):
		source_name = self.ui.accountFrom.currentText()
		target_name = self.ui.accountTo.currentText()
		clear_message = self.ui.clearMessage.toPlainText()
		
		with self.iso.unlockedWallet() as w:
			cipher = self.iso.getMemo(
				source_name,
				target_name,
				text=clear_message,
				data=None)
			
			self.ui.cipherMessage.setPlainText(json.dumps(cipher))
	
	def read_memo(self):
		cipher_message = self.ui.cipherMessage.toPlainText()
		data = json.loads(cipher_message)
		#showerror(str(data))
		
		with self.iso.unlockedWallet() as w:
			clear = self.iso.getMemo(None, None, data=data)
		
			set_combo(self.ui.accountFrom, clear["from"])
			set_combo(self.ui.accountTo, clear["to"])
			self.ui.clearMessage.setPlainText(clear["message"])
	
	#def generate_password(self):
	#	pass