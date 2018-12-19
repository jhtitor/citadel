from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.voting import Ui_VotingWindow

from .netloc import RemoteFetch
from .utils import *
import logging
log = logging.getLogger(__name__)
import json

from .transactionbuilder import QTransactionBuilder
from .createworker import WorkerWindow

class VotingWindow(QtWidgets.QDialog):
	
	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('isolator', None)
		self.accounts = kwargs.pop('accounts', [ ])
		self.activeAccount = kwargs.pop('account', None)
		self.proxyAccount = self.iso.getAccount(self.activeAccount["options"]["voting_account"])
		self.mode = kwargs.pop('mode', "create")
		self.asset = kwargs.pop('asset', None)
		super(VotingWindow, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_VotingWindow()
		
		ui.setupUi(self)
		
		stretch_table(self.ui.witnessTable, 2)
		stretch_table(self.ui.committeeTable, 2)
		stretch_table(self.ui.workersTable, 2)
		
		qmenu(self.ui.witnessTable, self.show_vote_submenu)
		qmenu(self.ui.committeeTable, self.show_vote_submenu)
		qmenu(self.ui.workersTable, self.show_vote_submenu)
		
		mw = self.iso.mainwin
		self.updaterWS = RemoteFetch(manager=mw.Requests)
		self.updaterCM = RemoteFetch(manager=mw.Requests)
		self.updaterWR = RemoteFetch(manager=mw.Requests)
		self.resync()
		self.proxy_toggle()
		self.refreshUi(1) # disable OK/Proxy buttons
		
		for account_name in self.accounts:
			if account_name == self.activeAccount["name"]:
				self.ui.accountBox.addItem(account_name)
			self.ui.accountProxy.addItem(account_name)
		
		mw = app().mainwin
		mw.uiAccountAssetLink(self.ui.accountBox, self.ui.updateFeeAsset)
		
		set_combo(self.ui.accountBox, self.activeAccount["name"])
		self.ui.accountBox.currentIndexChanged.emit(self.ui.accountBox.currentIndex())
		set_combo(self.ui.updateFeeAsset, "BTS", force=False)
		
		if not(mw.is_advancedmode()):
			hide = [ self.ui.updateFeeAsset, self.ui.updateFeeLabel ]
			for w in hide:
				w.hide()
		
		set_combo(self.ui.accountProxy, self.proxyAccount["name"], force=True)
		
		on_combo(self.ui.accountProxy, self.update_proxy)
		#self.resync()
		#return
		
		#i = 0
		
		self.ui.witnessTable.itemChanged.connect(self.witness_click)
		self.ui.committeeTable.itemChanged.connect(self.committee_click)
		self.ui.workersTable.itemChanged.connect(self.worker_click)
		
		self.ui.removeProxy.clicked.connect(self.remove_proxy)
		self.ui.restoreProxy.clicked.connect(self.restore_proxy)
		
		
		#self.ui.isBitasset.stateChanged.connect(self.bitasset_toggle)
		#self.ui.updateButton.clicked.connect(self.attempt_update)
		self.ui.buttonBox.accepted.connect(self.attempt_update)
		self.ui.buttonBox.rejected.connect(self.reject)
		#self.ui.buttonBox.clicked.connect(self.route_buttonbox)
		
		if self._proxy():
			self._oldProxy = self.proxyAccount["name"]
			self.ui.restoreProxy.setText(self.proxyAccount["name"])
			self.ui.removeProxy.setText(self.activeAccount["name"])
		else:
			self.ui.removeProxy.setVisible(False)
			self.ui.restoreProxy.setVisible(False)
		
	
	def route_buttonbox(self, button):
		if button == self.ui.buttonBox.button(QtGui.QDialogButtonBox.Ok):
			self.attempt_update()
		if button in [
			self.ui.buttonBox.button(QtGui.QDialogButtonBox.Cancel),
			self.ui.buttonBox.button(QtGui.QDialogButtonBox.Close) ]:
			self.reject()
	
	def _proxy(self):
		return self.proxyAccount["id"] != self.activeAccount["id"]
	
	def _votes(self, vote_id):
		return vote_id in self.proxyAccount["options"]["votes"]
	
	def update_proxy(self):
		name = self.ui.accountProxy.currentText().strip()
		self.proxyAccount = self.iso.getAccount(name)
		self.recheck()
		self.proxy_toggle()
	
	def remove_proxy(self):
		set_combo(self.ui.accountProxy, self.activeAccount["name"], force=True)

	def restore_proxy(self):
		set_combo(self.ui.accountProxy, self._oldProxy, force=True)

	def recheck(self):
		flag = QtCore.Qt.NoItemFlags
		if self.proxyAccount["id"] == self.activeAccount["id"]:
			flag |= QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled
		
		table = self.ui.witnessTable
		n = table.rowCount()
		for j in range(0, n):
			item = table.item(j, 0)
			ip = table.item(j, 3)
			data = item.data(99)
			if self._votes(data["vote_id"]):
				ip.setCheckState(1)
			else:
				ip.setCheckState(0)
			ip.setFlags(flag)
		
		table = self.ui.committeeTable
		n = table.rowCount()
		for j in range(0, n):
			item = table.item(j, 0)
			ip = table.item(j, 3)
			data = item.data(99)
			if self._votes(data["vote_id"]):
				ip.setCheckState(1)
			else:
				ip.setCheckState(0)
			ip.setFlags(flag)
		
		table = self.ui.workersTable
		n = table.rowCount()
		for j in range(0, n):
			item = table.item(j, 0)
			ip = table.item(j, 4)
			ic = table.item(j, 5)
			data = item.data(99)
			if self._votes(data["vote_for"]):
				ip.setCheckState(1)
			else:
				ip.setCheckState(0)
			if self._votes(data["vote_against"]):
				ic.setCheckState(1)
			else:
				ic.setCheckState(0)
			ip.setFlags(flag)
			ic.setFlags(flag)
	
	def proxy_toggle(self):
		return False
		if self.proxyAccount["id"] == self.activeAccount["id"]:
			e = True
		else:
			e = False
		self.ui.witnessTable.setEnabled(e)
		self.ui.committeeTable.setEnabled(e)
		self.ui.workersTable.setEnabled(e)
	
	def witness_click(self, item):
		pass
	def committee_click(self, item):
		pass
	def worker_click(self, item):
		row = item.row()
		col = item.column()
		acol = col + 1 if col == 4 else col - 1
		rel_item = self.ui.workersTable.item(row, acol)
		if item.checkState():
			rel_item.setCheckState(0)
	
	def collect_witness_votes(self, votes):
		table = self.ui.witnessTable
		cnt = 0
		n = table.rowCount()
		for j in range(0, n):
			item = table.item(j, 0)
			data = item.data(99)
			ip = table.item(j, 3)
			if ip.checkState():
				votes.append(data["vote_id"])
				cnt += 1
		return cnt
	
	def collect_committee_votes(self, votes):
		table = self.ui.committeeTable
		cnt = 0
		n = table.rowCount()
		for j in range(0, n):
			item = table.item(j, 0)
			data = item.data(99)
			ip = table.item(j, 3)
			if ip.checkState():
				votes.append(data["vote_id"])
				cnt += 1
		return cnt
	
	def collect_worker_votes(self, votes):
		table = self.ui.workersTable
		cnt = 0
		n = table.rowCount()
		for j in range(0, n):
			item = table.item(j, 0)
			data = item.data(99)
			ip = table.item(j, 3)
			ic = table.item(j, 4)
			if ip.checkState():
				votes.append(data["vote_for"])
				cnt += 1
			if ic.checkState():
				votes.append(data["vote_against"])
				cnt += 1
		return cnt
	
	def attempt_update(self):
		fee_asset = anyvalvis(self.ui.updateFeeAsset, None)#.currentText()
		
		voting_account = self.ui.accountProxy.currentText()
		voting_account = self.iso.getAccount(voting_account)
		
		num_witness = 0
		num_committee = 0
		votes = [ ]
		
		num_witness = self.collect_witness_votes(votes)
		num_committee = self.collect_committee_votes(votes)
		self.collect_worker_votes(votes)
		
		if voting_account["id"] != self.activeAccount["id"]:
			num_witness = self.activeAccount["options"]["num_witness"]
			num_committee = self.activeAccount["options"]["num_committee"]
			votes = self.activeAccount["options"]["votes"]
		
		prev_options = self.activeAccount["options"]
		new_options = {
			"voting_account": voting_account["id"],
			"memo_key": prev_options["memo_key"], # no change
			"num_witness": num_witness,
			"num_committee": num_committee,
			"votes": votes,
			"extensions": prev_options["extensions"] # no change
		}
		
		if dict_same(prev_options, new_options):
			showmsg("No change")
			self.reject()
			return False
		
		try:
			r = QTransactionBuilder.QUpdateAccount(
				self.activeAccount["name"],
				None, # owner key (no change)
				None, # active key (no change)
				self.activeAccount["options"]["memo_key"],
				self.proxyAccount["name"],
				num_witness,
				num_committee,
				votes,
				fee_asset=fee_asset,
				isolator=self.iso
			)
		except Exception as error:
			showexc(error)
			return False
		
		if r:
			self.accept()
	
	def close(self):
		self.updaterWS.cancel()
		self.updaterCM.cancel()
		self.updaterWR.cancel()

	def resync(self):
		self.updaterWS.fetch(
			self.mergeWitness_before, self.iso, True,
			ready_callback=self.mergeWitness_after,
			error_callback=self.mergeWitness_abort,
			ping_callback=self.ping_callback,
			description="Updating witnesses")
		
		self.updaterCM.fetch(
			self.mergeCommittee_before, self.iso, True,
			ready_callback=self.mergeCommittee_after,
			error_callback=self.mergeCommittee_abort,
			ping_callback=self.ping_callback,
			description="Updating committee members")
		
		self.updaterWR.fetch(
			self.mergeWorkers_before, self.iso, True,
			ready_callback=self.mergeWorkers_after,
			error_callback=self.mergeWorkers_abort,
			ping_callback=self.ping_callback,
			description="Updating workers")

	def mergeWitness_before(self, iso, passive, request_handler=None):
		
		witnesses = iso.getWitnesses(passive, lazy=False, request_handler=request_handler)
		for w in witnesses:
			if hasattr(w, '_account'): continue
			w._account = w.account
		
		return (witnesses, passive, )

	def mergeWitness_after(self, request_id, args):
		(witnesses, passive, ) = args
		
		flag = QtCore.Qt.NoItemFlags
		if self.proxyAccount["id"] == self.activeAccount["id"]:
			flag |= QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled
		
		table = self.ui.witnessTable
		table.setRowCount(0)
		
		j = -1
		for w in witnesses:
			j += 1
			table.insertRow(j)
			item = set_col(table, j, 0, w["id"], data = w)
			set_col(table, j, 1, w._account["name"])
			set_col(table, j, 2, w["url"])
			ip = set_col(table, j, 3, w["total_votes"], align="right")
			if self._votes(w["vote_id"]):
				ip.setCheckState(1)
			else:
				ip.setCheckState(0)
			ip.setFlags(flag)
			#set_itemflags(item, checked=checked, checkable=True, selectable=True, core=table)
		
		#for w in witnesses:
		#	print("***")
		#	for k, v in w.items():
		#		print(k, "->",v)
				#print(w.json())
		# refresh info
		#self.refreshUi()
	
	def mergeWitness_abort(self, request_id, error):
		log.error("Failed to get witnesses: %s", str(error))

	def mergeCommittee_before(self, iso, passive, request_handler=None):
		
		members = iso.getCommittee(passive, lazy=False, request_handler=request_handler)
		for m in members:
			if hasattr(m, '_account'): continue
			m._account = m.account
		
		return (members, passive, )
	
	def mergeCommittee_after(self, request_id, args):
		(members, passive, ) = args
		
		flag = QtCore.Qt.NoItemFlags
		if self.proxyAccount["id"] == self.activeAccount["id"]:
			flag |= QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled
		
		#for c in members:
		#	for k, v in c.items():
		#		print(k, "->",v)
		#		#print(w.json())
		
		table = self.ui.committeeTable
		table.setRowCount(0)
		j = -1
		for w in members:
			j += 1
			table.insertRow(j)
			item = set_col(table, j, 0, w["id"], data = w)
			set_col(table, j, 1, w._account["name"])
			set_col(table, j, 2, w["url"])
			ip = set_col(table, j, 3, int(w["total_votes"]), align="right")
			if self._votes(w["vote_id"]):
				ip.setCheckState(1)
			else:
				ip.setCheckState(0)
			ip.setFlags(flag)
		
		#self.refreshUi()
	
	def mergeCommittee_abort(self, request_id, error):
		log.error("Failed to get committee: %s", str(error))

	def mergeWorkers_before(self, iso, passive, request_handler=None):
		
		workers = iso.getWorkers(passive, lazy=False, request_handler=request_handler)
		for w in workers:
			if hasattr(w, '_account'): continue
			w._account = w.account
		
		return (workers, passive, )
	
	def mergeWorkers_after(self, request_id, args):
		(workers, passive, ) = args
		
		flag = QtCore.Qt.NoItemFlags
		if self.proxyAccount["id"] == self.activeAccount["id"]:
			flag |= QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled
		
		#for w in workers:
		#	print("WORKER>>>>")
		#	for k, v in w.items():
		#		print(k, "->",v)
		#		#print(w.json())
		
		table = self.ui.workersTable
		table.setRowCount(0)
		j = -1
		for w in workers:
			j += 1
			table.insertRow(j)
			set_col(table, j, 0, w["id"], data = w)
			set_col(table, j, 1, w["name"])#._account["name"])
			set_col(table, j, 2, w["url"])
			set_col(table, j, 3, w["work_begin_date"].strftime("%Y-%m-%d")
			                   + " - "
			                   + w["work_end_date"].strftime("%Y-%m-%d"))
			ip = set_col(table, j, 4, int(w["total_votes_for"]), align="right")
			ic = set_col(table, j, 5, int(w["total_votes_against"]), align="right")
			#set_itemflags(item, checked=checked, checkable=True, selectable=True, core=table)
			#ip.setCheckState(True)
			#ic.setCheckState(True)
			if self._votes(w["vote_for"]):
				ip.setCheckState(1)
			else:
				ip.setCheckState(0)
			if self._votes(w["vote_against"]):
				ic.setCheckState(1)
			else:
				ic.setCheckState(0)
			ip.setFlags(flag)
			ic.setFlags(flag)
		
		#self.refreshUi()
	
	def mergeWorkers_abort(self, request_id, error):
		log.error("Failed to get workers: %s", str(error))
	
	def ping_callback(self, request_id, o):
		# refreshUi is going to count active processes
		# and will include THIS one, even as it's finished
		from .work import Request
		mod = 0
		if (o == Request.PT_FINISHED) or (o == Request.PT_CANCELLED):
			mod = -1
		# so we cheat add subtract 1 from busy count
		self.refreshUi(0)#mod)
	
	def refreshUi(self, mod=0):
		text = delim = ""
		busy = 0
		# Inform about background tasks:
		bgtop = self.iso.mainwin.Requests.top()
		for task in bgtop:
			(cancelled, desc, c, p) = task
			if cancelled or not(desc):
				continue
			if c in ['mergeWitness_before',
				'mergeCommittee_before',
				'mergeWorkers_before']:
				busy += 1
			else:
				continue
			text = text + delim + desc
			delim = " | "
		busy += mod
		if busy:
			text = text + delim + " Please wait..."
		else:
			text = ""
		self.ui.statusText.setText("" + text)
		
		button = self.ui.buttonBox.button(QtGui.QDialogButtonBox.Ok)
		#button = self.updateButton
		button.setEnabled(not(busy))
		self.ui.accountProxy.setEnabled(not(busy))
		#if busy:
		#	self.ui.updateButton.setEnabled(False)
		#else:
		#	self.ui.updateButton.setEnabled(True)
		
	def _get_table(self):
		page = self.ui.tabWidget.currentIndex()
		table = None
		if page == 1:
			table = self.ui.witnessTable
		if page == 2:
			table = self.ui.committeeTable
		if page == 3:
			table = self.ui.workersTable
		return table
	
	def show_vote_submenu(self, position):
		menu = QtGui.QMenu()
		qaction(self, menu, "Copy URL", self._copy_url)
		qaction(self, menu, "Copy Name", self._copy_name)
		table = self._get_table()
		if table == self.ui.workersTable:
			menu.addSeparator()
			qaction(self, menu, "Details", self._worker_details)
		qmenu_exec(table, menu, position)
		
	
	def _copy_url(self):
		table = self._get_table()
		j = table_selrow(table)
		if j <= -1: return
		url = table.item(j, 2).text()
		if not len(url.strip()):
			return
		qclip(url)
	
	def _copy_name(self):
		table = self._get_table()
		j = table_selrow(table)
		if j <= -1: return
		name = table.item(j, 1).text()
		if not len(name.strip()):
			return
		qclip(name)
	
	def _worker_details(self):
		table = self._get_table()
		j = table_selrow(table)
		if j <= -1: return
		worker = table_coldata(table, j, 0)
		
		win = WorkerWindow(worker=worker, mode="view", parent=self)
		win.exec_()
