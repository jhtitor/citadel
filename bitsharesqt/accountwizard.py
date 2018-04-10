from PyQt4 import QtCore, QtGui
from uidef.accountwizard import Ui_accountWizard

from .utils import *
import logging
log = logging.getLogger(__name__)

from rpcs.btsfaucet import BTSFaucet
from .bootstrap import KnownFaucets

#from bitshares import BitShares
from bitshares.account import Account
from bitsharesbase.account import PasswordKey
from bitsharesbase.account import PrivateKey
from bitsharesbase.account import BrainKey

from .transactionbuilder import QTransactionBuilder

class AccountWizard(QtGui.QWizard):

	PAGE_INTRO = 0
	PAGE_NEW_PASS = 1
	PAGE_OLD_PASS = 2
	PAGE_NEW_BRAIN = 3
	PAGE_OLD_BRAIN = 4
	PAGE_REGISTER = 5
	PAGE_KEYS = 6

	def __init__(self, *args, **kwargs):
		self.iso = kwargs.pop('isolator', None)
		self.account_names = kwargs.pop('registrars', [ ])
		self.activeAccounts = kwargs.pop('active', None)
		super(AccountWizard, self).__init__(*args, **kwargs)
		self.ui = ui = Ui_accountWizard()
		ui.setupUi(self)

		#self._curid = -1
		#self.currentIdChanged.connect(self._cur_id)

		#self.button(QtGui.QWizard.NextButton).clicked.connect(self.next)

		self.ui.keysPage.registerField("keys", self.ui.privateKeys)
		self.ui.generatePassword.clicked.connect(self.generate_password)

		fb = self.ui.faucetBox
		for name, url, refurl, factory in KnownFaucets:
			fb.addItem(name, (url, refurl))
		
		rb = self.ui.registrarBox
		for name in self.account_names:
			rb.addItem(name)
		
		if len(self.account_names) > 0:
			self.ui.faucetBox.hide()
			self.ui.faucetLabel.hide()
		else:
			self.ui.registrarBox.hide()
			self.ui.registrarLabel.hide()
		
	
#	def _cur_id(self, id):
#		self._curid = id
#	
#	def currentId(self):
#		return self._curid
	
	def generate_password(self):
		pw = generate_webwalletlike_password()
		
		self.ui.inventPassword.setText(pw)
		self.ui.inventPassword.setReadOnly(True)
	
	def validateCurrentPage(self):
		c = self.currentId()
		
		if (c == AccountWizard.PAGE_INTRO):
			self.ui.passwordConfirm.setText("")
			
			if self.ui.rNewBrain.isChecked():
				generated = self.ui.brainkeyView.toPlainText()
				if not generated:
					bk = BrainKey() # this will generate a new one
					self.ui.brainkeyView.setPlainText(bk.get_brainkey())
					
			if self.ui.rOldBrain.isChecked():
				self.ui.brainkeyView.setPlainText("")
			
			#self.button(QtGui.QWizard.NextButton).clicked.emit(True)
		
		if (c == AccountWizard.PAGE_OLD_BRAIN):
			entered = self.ui.brainkeyEdit.toPlainText()
			if not(entered):
				return False
			
			bk = BrainKey(entered)
			
			generated = self.ui.brainkeyView.toPlainText()
			if generated:
				# compare normalized brainkeys
				old_bk = BrainKey(generated)
				if old_bk.get_brainkey() != bk.get_brainkey():
					showerror("Brainkey does not match the generated one", additional="If you lose your brainkey, you will lose your account and funds.")
					return False
			
			# TODO: proper way to verify brain key?
			if len(bk.get_brainkey()) < 25 * 2:
				showerror("This does not look like a brain key")
				return False
			
			bk.sequence = 0
			owner_key = bk.get_private()
			active_key_index = 0 #find_first_unused_derived_key_index( owner_key )
			active_key = owner_key.derive_private_key(active_key_index)
			memo_key_index = 0 #find_first_unused_derived_key_index( active_key )
			memo_key = active_key.derive_private_key(memo_key_index)
			
			#bk.sequence = 0; active_key = bk.get_private()
			#bk.sequence = 1; owner_key = bk.get_private()
			#bk.sequence = 2; memo_key = bk.get_private()
			
			privs = ""
			privs += str(active_key) + "\n"
			privs += str(owner_key) + "\n"
			privs += str(memo_key) + "\n"
			
			print("Private keys (a,o,m)" + privs)
			
			#pubs = ""
			#pubs += str(active_key.pubkey) + "\n"
			#pubs += str(owner_key.pubkey) + "\n"
			#pubs += str(memo_key.pubkey) + "\n"
			
			self.ui.pubkeyOwner.setText( str(owner_key.pubkey) )
			self.ui.pubkeyActive.setText( str(active_key.pubkey) )
			self.ui.pubkeyMemo.setText( str(memo_key.pubkey) )
			
			#self.ui.publicKeys.setPlainText(pubs)
			self.ui.privateKeys.setPlainText(privs)
		
		if (c == AccountWizard.PAGE_NEW_PASS):
			account_name= self.ui.inventAccount.text()
			password = self.ui.inventPassword.text()
			if not(account_name) or not(password):
				return False
			
			if len(password) < 12:
				showerror("Password should contain at least 12 characters")
				return False
			
			self.ui.oldAccount.setText(account_name)
			self.ui.inventPassword.setReadOnly(True)
			self.ui.passwordConfirm.setText("Confirm your password")
		
		if (c == AccountWizard.PAGE_OLD_PASS):
			account_name= self.ui.oldAccount.text()
			password = self.ui.oldPassword.text()
			if not(account_name) or not(password):
				return False
			
			old_password = self.ui.inventPassword.text()
			if old_password and (password != old_password):
				showerror("Password you entered during previous step does not match this one", additional="If you lose your password, you will lose your account and funds.")
				return False
			
			active_key = PasswordKey(account_name, password, role="active")
			owner_key = PasswordKey(account_name, password, role="owner")
			memo_key = PasswordKey(account_name, password, role="memo")
			
			#print("Active key:", active_key.get_private(), active_key.get_public())
			#print("Owner key:", owner_key.get_private(), owner_key.get_public())
			#print("Memo key:", memo_key.get_private(), memo_key.get_public())
			
			privs = ""
			privs += str(active_key.get_private()) + "\n"
			privs += str(owner_key.get_private()) + "\n"
			privs += str(memo_key.get_private()) + "\n"
			
			print("Private keys (a,o,m)\n" + privs)
			
			#pubs = ""
			#pubs += str(active_key.get_public()) + "\n"
			#pubs += str(owner_key.get_public()) + "\n"
			#pubs += str(memo_key.get_public()) + "\n"
			
			self.ui.pubkeyOwner.setText( str(owner_key.get_public()) )
			self.ui.pubkeyActive.setText( str(active_key.get_public()) )
			self.ui.pubkeyMemo.setText( str(memo_key.get_public()) )
			
			self.ui.accountName.setText(account_name)
			#self.ui.publicKeys.setPlainText(pubs)
			
			self.ui.accountEdit.setText(account_name)
			self.ui.privateKeys.setPlainText(privs)
		
		if (c == AccountWizard.PAGE_REGISTER):
			account_name = self.ui.accountName.text()
			
			self.ui.accountEdit.setText(account_name)
			
			#pubkeys = self.ui.publicKeys.toPlainText()
			#privkeys = self.ui.privateKeys.toPlainText()
			
			owner_key = self.ui.pubkeyOwner.text()
			active_key = self.ui.pubkeyActive.text()
			memo_key = self.ui.pubkeyMemo.text()
			
			if not account_name:
				showerror("Please enter account name", account_name)
				return False
			
			if not owner_key or not active_key or not memo_key:
				showerror("Please enter all three (owner, active, memo) keys")
				return False
			
			
			if self.ui.faucetBox.isVisible() == True:
				#config = self.iso.store.configStorage
				proxy = self.iso.get_proxy_config()
				print("Faucet using proxy", proxy)
				selected = self.ui.faucetBox.currentText()
				faucet = None
				for name, url, refurl, factory in KnownFaucets:
					if name == selected:
						faucet = BTSFaucet(url, refurl, proxyUrl=proxy)
						break
				
				if not faucet:
					showerror("No faucet selected")
					return False
				
				try:
					reg = faucet.register(account_name,
						owner_key, active_key, memo_key,
						refcode=None, referrer=None
					)
				except Exception as e:
					import traceback
					traceback.print_exc()
					showexc(e)
					return False
				except:
					import traceback
					traceback.print_exc()
					return False
				
				from pprint import pprint
				print("REG:")
				pprint(reg)
			
			if self.ui.registrarBox.isVisible() == True:
				
				selected = self.ui.registrarBox.currentText()
				
				data = {
					'name': account_name,
					'owner_key': owner_key,
					'active_key': active_key,
					'memo_key': memo_key,
				}
				try:
					trx = QTransactionBuilder.QRegisterAccount(
						selected,
						selected,
						data, 
						isolator=self.iso)
					if not trx:
						return False
				except BaseException as error:
					showexc(error)
					return False
			
			self.ui.accountStatus.setText("")
			self.ui.privkeysStatus.setText("Your account has been registered.")
			#self.button(QtGui.QWizard.NextButton).clicked.emit(True)
		
		return True
	
	def nextId(self):
		c = self.currentId()
		
		if (c == AccountWizard.PAGE_INTRO):
			if self.ui.rNewBrain.isChecked():
				return AccountWizard.PAGE_NEW_BRAIN
			if self.ui.rNewPass.isChecked():
				return AccountWizard.PAGE_NEW_PASS
			if self.ui.rOldBrain.isChecked():
				return AccountWizard.PAGE_OLD_BRAIN
			if self.ui.rOldPass.isChecked():
				return AccountWizard.PAGE_OLD_PASS
			if self.ui.rOldKeys.isChecked():
				return AccountWizard.PAGE_KEYS
		
		if (c == AccountWizard.PAGE_OLD_BRAIN):
			if self.ui.rOldBrain.isChecked():
				return AccountWizard.PAGE_KEYS
			return AccountWizard.PAGE_REGISTER
		
		if (c == AccountWizard.PAGE_OLD_PASS):
			if self.ui.rOldPass.isChecked():
				return AccountWizard.PAGE_KEYS
			return AccountWizard.PAGE_REGISTER
		
		if (c == AccountWizard.PAGE_REGISTER):
			return -1
		
		if (c == AccountWizard.PAGE_KEYS):
			return -1
		
		return c + 1
