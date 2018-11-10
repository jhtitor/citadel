from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.walletwizard import Ui_walletWizard

from .utils import *
import logging
log = logging.getLogger(__name__)

from .isolator import BitsharesIsolator
from bitsharesextra.storage import BitsharesStorageExtra, DataDir
import configparser, os
class RecentWallets(object):
	max_entries = 10
	recent = [ ]
	@classmethod
	def init(self):
		datadir = DataDir.preflight(filename=False)
		confpath = os.path.join(datadir, "config.ini")
		self.load_config(confpath)
	@classmethod
	def last_wallet(self):
		if len(self.recent) < 1:
			return None
		return self.recent[0]
	@classmethod
	def load_config(self, path):
		self.config_path = path
		log.info("Loading config file %s" %  path)
		try:
			cp = configparser.ConfigParser()
			cp.read(path)
			cp.sections()
			n = int(cp['Recent']['num_entries'])
			if n > self.max_entries: self.max_entries = n
			for i in range(1, n + 1):
				try:
					self.recent.append( cp['Recent'][("file%d" % i)] )
				except KeyError:
					break
				except:
					import traceback
					traceback.print_exc()
					break
			return True
		except Exception as e:
			import traceback
			traceback.print_exc()
			return e
		return None
	@classmethod
	def dump_config(self, path=None):
		if path is None: path = self.config_path
		else: self.config_path = path
		log.debug("Saving config to %s" % path)
		with open(path, "w") as f:
			f.write("; this file is auto-generated\n")
			f.write("[Recent]\n")
			f.write("num_entries = %d\n" % RecentWallets.max_entries)
			i = 0
			for path in self.recent:
				i += 1
				f.write("file%d = %s\n" %(i, path))
	@classmethod
	def push_wallet(self, path):
		if path in self.recent:
			i = self.recent.index(path)
			self.recent.pop(i)
		#self.recent.append(path) #prepend!
		self.recent.insert(0, path)
		self.dump_config()
	@classmethod
	def pick_newpath(self):
		base = DataDir.preflight(filename=False)
		fine = False
		j = 1
		while not(fine):
			add = ("_%d" % j) if j > 1 else ""
			name = "default" + add + ".bts"
			path = os.path.join(base, name)
			if not(os.path.exists(path)):
				fine = True
			j = j + 1
		return path

class WalletWizard(QtWidgets.QWizard):

	PAGE_INTRO = 0
	PAGE_NEW_PASS = 1
	PAGE_LAST = 2

	def __init__(self, *args, **kwargs):
		#self.iso = kwargs.pop('isolator', None)
		#self.account_names = kwargs.pop('registrars', [ ])
		#self.activeAccount = kwargs.pop('active', None)
		self.newOnly = kwargs.pop('newOnly', False)
		super(WalletWizard, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_walletWizard()
		ui.setupUi(self)

		if self.newOnly:
			self.ui.rRecentWallet.setVisible(False)
			self.ui.rOpenWallet.setVisible(False)
			self.ui.recentList.setVisible(False)
		self.ui.newPath.setText(RecentWallets.pick_newpath())
		self.ui.newChange.clicked.connect(self.change_newpath)

		# "return"
		self._wallet_path = None
		self._is_new = False
		self._master_password = None

		rl = self.ui.recentList
		for path in list(RecentWallets.recent):
			rl.addItem(path)
		rl.itemDoubleClicked.connect(self.quick_recent)
		self.ui.rNewWallet.toggled.connect(self._refresh_intro)
		self.ui.rRecentWallet.toggled.connect(self._refresh_intro)
		self.ui.rOpenWallet.toggled.connect(self._refresh_intro)
		self._refresh_intro()
		

	def run(self):
		r = self.exec_()
		if r == 0:
			return False, None, None, None
		return True, self._wallet_path, self._is_new, self._master_password
	
	def change_newpath(self):
		path = self.ui.newPath.text() #DataDir.preflight()
		path, _ = QtGui.QFileDialog.getSaveFileName(self, 'New wallet file', path, "PyBitshares Wallet (*.bts *.sqlite)")
		if not path:
			return
		self.ui.newPath.setText(path)
	
	def _refresh_intro(self):
		#button groups for each option
		g1 = [ self.ui.newPath, self.ui.newChange ]
		g2 = [ self.ui.recentList ]
		g3 = [ ]
		if self.ui.rNewWallet.isChecked():
			enable = g1
			disable = g2 + g3
		elif self.ui.rRecentWallet.isChecked():
			enable = g2
			disable = g1 + g3
		elif self.ui.rOpenWallet.isChecked():
			enable = g3
			disable = g1 + g2
		for o in enable:
			o.setEnabled(True)
		for o in disable:
			o.setEnabled(False)
	
	def quick_recent(self):
		box = self.ui.recentList
		if not box.currentIndex().isValid():
			return False
		path = box.currentItem().text()
		if not(path):
			return False
		self.next()

	def validateCurrentPage(self):
		c = self.currentId()
		
		if (c == WalletWizard.PAGE_INTRO):
			self.ui.masterPassword.setText("")
			self.ui.masterConfirm.setText("")
			
			if self.ui.rNewWallet.isChecked():
				path = self.ui.newPath.text().strip()
				if not path:
					showmsg("Pick file location for the new wallet.")
					return False
				self.ui.passwordWalletPath.setText(path)
				self.ui.finalWalletPath.setText(path)
				self._wallet_path = path
				if os.path.exists(path):
					showerror("File %s already exists, and for your own sake, WILL NOT be overwritten." % path)
					return False
			
			if self.ui.rRecentWallet.isChecked():
				box = self.ui.recentList
				if not box.currentIndex().isValid():
					return False
				path = box.currentItem().text()
				self._wallet_path = path
			
			if self.ui.rOpenWallet.isChecked():
				return True
		
		if (c == WalletWizard.PAGE_NEW_PASS):
			password = self.ui.masterPassword.text()
			confirm = self.ui.masterConfirm.text()
			if password != confirm:
				showerror("Password and confirmation do not match.")
				return False
			if password == "":
				yes = askyesno("You have entered an EMPTY password, which is very insecure. \n\nAre you sure you want your master password to be empty?")
				if not yes:
					return False
			path = self.ui.passwordWalletPath.text()
			self.ui.finalWalletPath.setText(path)
			self._wallet_path = path
			self._master_password = password
			self._is_new = True
			
			if not password: password = 'default'
			from bitshares.wallet import Wallet
			try:
				store = BitsharesStorageExtra(path, create=True)
				wallet = Wallet(rpc=None, key_store=store.keyStorage, blind_store=store.blindStorage)
				wallet.newWallet(password) # BROKEN in latest bitshares
				store.keyStorage.unlock(password) # this actually sets the new master password...
				iso = BitsharesIsolator(node=None) # hacky, only used for
				iso.wallet = wallet                # bootstrap
				iso.store = store                  # TODO: move it here
				iso.bootstrap_wallet()             # !
			except Exception as error:
				showexc(error)
				return False
		
		return True
	
	def nextId(self):
		c = self.currentId()
		
		if (c == WalletWizard.PAGE_INTRO):
			if self.ui.rNewWallet.isChecked():
				return WalletWizard.PAGE_NEW_PASS
			
			if self.ui.rRecentWallet.isChecked():
				self.accept()
				return -1
		
			if self.ui.rOpenWallet.isChecked():
				path = DataDir.preflight()
				path, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open wallet file', path, "PyBitshares wallet (*.bts *.sqlite)")
				if not path:
					return False
				self._wallet_path = path
				self.accept()
				return -1
		
		if (c == WalletWizard.PAGE_LAST):
			return -1
		
		return c + 1

