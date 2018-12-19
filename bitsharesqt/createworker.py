from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.createworker import Ui_CreateWorker

from .utils import *
import json
import logging
log = logging.getLogger(__name__)

import datetime
from .transactionbuilder import QTransactionBuilder

GRAPHENE_MAX_SHARE_SUPPLY = 1000000000000000

class WorkerWindow(QtWidgets.QDialog):
	
	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('isolator', None)
		self.accounts = kwargs.pop('accounts', [ ])
		self.activeAccount = kwargs.pop('account', None)
		self.mode = kwargs.pop('mode', "create")
		self.worker = kwargs.pop('worker', None)
		self.contacts = kwargs.pop('contacts', [ ])
		super(WorkerWindow, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_CreateWorker()
		
		ui.setupUi(self)
		
		mw = app().mainwin
		mw.uiAccountAssetLink(self.ui.accountBox, self.ui.feeAsset)
		for account_name in self.accounts:
			self.ui.accountBox.addItem(account_name)
		
		if not(mw.is_advancedmode()) or self.mode == "view":
			hide = [ self.ui.feeAsset, self.ui.feeAssetLabel ]
			for w in hide:
				w.hide()
		
		self.ui.buttonBox.clicked.connect(self.route_buttonbox)
		
		self.setupMode(self.mode)
		
		if self.worker:
			self.setupWorker(self.worker)
			return
		
		if self.activeAccount:
			set_combo(self.ui.accountBox, self.activeAccount["name"])
		
		self.ui.dailyPaySpin.setMaximum(GRAPHENE_MAX_SHARE_SUPPLY)
		
		now = datetime.datetime.utcnow()
		year = datetime.timedelta(seconds=3600*24*365)
		
		self.ui.startDate.setMinimumDateTime(now)
		self.ui.startDate.setDateTime(now)
		self.ui.endDate.setMinimumDateTime(now)
		self.ui.endDate.setDateTime((now+year))

	
	def route_buttonbox(self, button):
#		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Apply):
		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Ok):
			if self.mode == "create":
				self.attempt_create()
			if self.mode == "view":
				self.accept()
			#if self.mode == "edit":
			#	self.attempt_update()
		
		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Cancel):
			self.reject()
		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Close):
			self.reject()
	
	def setupWorker(self, worker):
		set_combo(self.ui.accountBox, worker._account["name"])
		type_id, data = worker["worker"]
		days = None
		if type_id == 0: types = "refund"
		if type_id == 1: types = "vesting"
		if type_id == 2: types = "burn"

		self.ui.nameEdit.setText(worker["name"])
		self.ui.urlEdit.setText(worker["url"])
		self.ui.dailyPaySpin.setValue(worker["daily_pay"] / 100000)
		self.ui.startDate.setDateTime(worker["work_begin_date"])
		self.ui.endDate.setDateTime(worker["work_end_date"])
		set_combo(self.ui.typeCombo, types)

		# TODO: determine real value
		self.ui.daysLabel.setVisible(False)
		self.ui.daysSpin.setVisible(False)

		wi = [ self.ui.nameEdit,
		    self.ui.urlEdit, self.ui.dailyPaySpin,
		    self.ui.startDate, self.ui.endDate,
		    self.ui.daysSpin,
		]
		for w in wi:
			w.setReadOnly(True)

		wi = [ self.ui.accountBox, self.ui.typeCombo,
		]
		for w in wi:
			w.setEnabled(False)

		return
	
	def setupMode(self, mode):
		if mode == "create":
			pass
	
	def attempt_create(self):
		fee_asset = anyvalvis(self.ui.feeAsset, None)
		
		name = self.ui.nameEdit.text().strip()
		if not name:
			self.ui.nameEdit.setFocus()
			return
		
		url = self.ui.urlEdit.text().strip()
		if not url:
			self.ui.urlEdit.setFocus()
			return
		
		worker_type = self.ui.typeCombo.currentText()
		vesting_days = int(self.ui.daysSpin.value())
		daily_pay = float(self.ui.dailyPaySpin.value())
		
		begin_date = self.ui.startDate.dateTime().toPyDateTime()
		end_date = self.ui.endDate.dateTime().toPyDateTime()
		
		if end_date < begin_date:
			self.ui.endDate.setFocus()
			return
		
		account_name = self.ui.accountBox.currentText().strip()
		if not account_name:
			self.ui.accountBox.setFocus()
			return
		
#		worker_account = self.iso.getAccount(account_name)
#		try:
#			options = self.collect_options()
#		except Exception as e:
#			showexc(e)
#			return
		
		r = QTransactionBuilder.QCreateWorker(
			account_name,
			name, url,
			begin_date, end_date,
			daily_pay, worker_type, vesting_days,
			fee_asset=fee_asset,
			
			isolator=self.iso
		)
		
		if r:
			self.accept()
	
	def attempt_update(self):
		fee_asset = anyvalvis(self.ui.feeAsset, None)
		return
