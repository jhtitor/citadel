# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.chatserver import Ui_ChatServerTab
_translate = QtCore.QCoreApplication.translate

from PyQt5.QtCore import pyqtSlot


from bitsharesqt.chattab import ChatTab
from .tabwrangler import WindowWithTabWrangler

from bitshares.blind import receive_blind_transfer

from rpcs.bitshareschat._http import BitSharesChatHTTP
from rpcs.bitshareschat._websocket import BitSharesChatWS
from rpcs.bitshareschat.filedata import parseMessage
from rpcs.bitshareschat.filedata import fileToDataURI
from rpcs.bitshareschat._websocket import MutexSet
from collections import OrderedDict as od
import queue

from PyQt5.QtGui import QTextCursor

from .netloc import RemoteFetch
from .utils import *
import json
import datetime

import logging
log = logging.getLogger(__name__)

import os
import time

class MSDict(dict):
	def add(self, key, msgid):
		if not(key in self):
			self[key] = MutexSet()
		self[key].add(msgid)
	def remove(self, key, msgid):
		if not(key in self):
			return
		self[key].remove(msgid)

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class ChatServerTab(QtWidgets.QWidget, WindowWithTabWrangler):
	
	def __init__(self, *args, **kwargs):
		self.ping_callback = kwargs.pop("ping_callback", None)
		self.iso = kwargs.pop("isolator", None)
		super(ChatServerTab, self).__init__(*args, **kwargs)
		self.ui = Ui_ChatServerTab()
		self.ui.setupUi(self)
		
		self._index = 6
		
		self.ui.openChat.clicked.connect(self.open_new_chat)
		self.ui.openRoom.clicked.connect(self.open_new_room)
		
		self.ui.tabWidget.currentChanged.connect(self.tab_switched)
		
		self.stash = [ ]
		
		self.messages = od() # list of all messages
		self.over_read = {} # statuses for messages we don't have yet
		self.privkeys = {}
		self.roomkeys = {}
		
		self._preserve_lastmsgid = { }
		self.known_expansions = { } # pubkey -> label tuple
		app().abort_everything.connect(self._abort)
		
		self.setup_ws_signals()
		
		# Periodic updater for HTTP rpc
		self.chat_delay_base = 15000
		self.chat_delay_interval = 3000
		self.chat_delay = self.chat_delay_base
		self.chat_update_timer = qtimer(self.chat_delay_interval, self.sync_messages)
		self.must_resync = True
		self.needRedraw = True

		mw = self.iso.mainwin
		
		self.updater = RemoteFetch(manager=mw.Requests)
		self.updating = False

		self.sender_ = RemoteFetch(manager=mw.Requests)
		self.sending = False
		self.send_queue = queue.Queue() # danger

		self.verifier = RemoteFetch(manager=mw.Requests)
		self.verifying = False
		self.verify_queues = MSDict() #MutexSet()

		self.downloader = RemoteFetch(manager=mw.Requests)
		self.downloading = False
		self.download_queue = [ ] # danger

		self.uploader = RemoteFetch(manager=mw.Requests)
		self.uploading = False
		self.upload_queue = [ ] # danger

		self.initializer = RemoteFetch(manager=mw.Requests)
		self.initializing = False
		self.initialized = False
		self.retry_init = False

		self.config = None
		self.rpc = None
		self.ws = None
		self.motd = None

	def refreshUi_ping(self, w=None,x=None):
		pass

	def loadRooms(self):
		store = self.iso.store.chatroomStorage
		rooms = store.getRooms()
		from_key_or_label = self.from_pub
		for room in rooms:
			if room['server'] != self.server_url:
				continue
			tab = self.openRoom(from_key_or_label, room['name'], save=False, to_front=False)
			tab.needRedraw = True

	def initialize(self, from_key_or_label, server_url):
		from_key, from_icon, from_label = self.keyExpandLabel(from_key_or_label, force_local=True)
		priv_key = self.iso.getPrivateKeyForPublicKeys([from_key])[0]
		self.server_url = server_url
		self.from_pub = from_key
		self.privkeys = {
			str(from_key): priv_key
		}
		zerotab = self.ui.tabWidget.widget(0)
		self.setTabTitle(zerotab, server_url)
		self.setTabIcon(zerotab, "server")
		
		self.start_init()
		self.refreshUi()

	def start_init(self):
		priv = self.privkeys[self.from_pub]
		self.initializing = True
		self.initializer.fetch(
			self.setupConnection, str(priv), self.server_url,
			ready_callback=self.initialize_after,
			error_callback=self.initialize_error
		)

	def setupConnection(self, priv_key, server_url):
		proxyUrl = self.iso.get_proxy_config()
		httpUrl, wsUrl = BitSharesChatHTTP.discover(server_url, proxyUrl=proxyUrl)
		return (httpUrl, wsUrl, priv_key)

	def initialize_error(self, uid, error):
		self.initializing = False
		if self.retry_init == False:
			showexc(error)
		self.retry_init = True
		self.refreshUi(error=error)

	def initialize_after(self, uid, args):
		self.initializing = False
		(httpUrl, wsUrl, priv_key) = args
		proxyUrl = self.iso.get_proxy_config()
		self.rpc = BitSharesChatHTTP(priv_key, httpUrl, proxyUrl=proxyUrl)
		if wsUrl:
			self.ws = BitSharesChatWS(priv_key, wsUrl,
				on_update  =self.push_ws_update,
				on_connect =self.push_ws_connect,
				on_disconnect=self.push_ws_disconnect,
				proxyUrl=proxyUrl
			)
		self.loadRooms()
		self.initialized = True
		self.retry_init = False
		self.resync()
		self.refreshUi()



	@safeslot
	def open_new_chat(self):
		name = self.ui.contactAccount.currentText().strip()
		if not name:
			self.ui.contactAccount.setFocus()
			return False
		self.openChat(str(self.from_pub), name)

	def openChat(self, from_key_or_label, to_key_or_label):
		from_key, from_icon, from_label = self.keyExpandLabel(from_key_or_label, force_local=True)
		to_key, to_icon, to_label = self.keyExpandLabel(to_key_or_label, force_local=True)
		self.getmakeTab(from_key, to_key, to_front=True)

	@safeslot
	def open_new_room(self):
		from_key_or_label = self.iso.mainwin.activeAccount["name"]
		from_key, from_icon, from_label = self.keyExpandLabel(from_key_or_label, force_local=True)
		name = self.ui.roomAddress.currentText().strip()
		if not name:
			self.ui.roomAddress.setFocus()
			return False
		self.openRoom(from_key_or_label, name)

	def openRoom(self, from_key_or_label, name, save=True, to_front=True):
		from bitsharesbase.account import BrainKey
		to_bk = BrainKey(name)
		to_priv = to_bk.get_blind_private()
		to_key = str(to_priv.pubkey)
		to_icon = "room"
		to_label = name
		
		self.add_room_key(to_priv)
		
		
		self.known_expansions[to_key] = (to_key, to_icon, to_label)
		tab = self.getmakeTab(from_key_or_label, to_key, to_front=to_front)
		tab.setupRoom(from_key_or_label, name)
		
		if save:
			store = self.iso.store.chatroomStorage
			try:
				store.add(name, str(to_priv.pubkey), self.server_url)
			except KeyError:
				pass
		
		return tab

	def add_room_key(self, to_priv):
		pub = str(to_priv.pubkey)
		self.privkeys[pub] = str(to_priv)
		self.roomkeys[pub] = str(to_priv)
		self.rpc.subscribe(to_priv)
		if self.ws:
			self.ws.subscribe(to_priv)

	def getmakeTab(self, from_key, to_key, to_front=False):
		user_key = None
		other_key = None
		
		if str(from_key) in self.roomkeys:
			other_key = from_key
			user_key = to_key
		elif str(to_key) in self.roomkeys:
			other_key = to_key
			user_key = from_key
		elif str(from_key) in self.privkeys:
			user_key = from_key
			other_key = to_key
		elif str(to_key) in self.privkeys:
			user_key = to_key
			other_key = from_key
		else:
			raise ValueError("Neither key is yours")

		tag = ">" + other_key

		args = (user_key, other_key)
		tab = self.restoreTab(ChatTab, self.addChatTab, args, tag, to_front=to_front)
		tab.setupConnection(*args)
		
		return tab

	def addChatTab(self, args, tag):
		key_from, key_to = args
		ui = self.ui
		
		tab = ChatTab(ping_callback=self.refreshUi_ping,
				isolator=self.iso,
				parentobj=self)
		
		tab._tags = [
			tag,
		]
		
		tab._title = ""
		tab._icon = None
		
		return tab
	
	def close(self): # gets called on tab destruction
		self._abort()
		self.sender_.cancel()
		self.updater.cancel()
		self.downloader.cancel()
		self.uploader.cancel()
		self.chat_update_timer.stop()

	def _abort(self): # gets called on "abort_everything" signal
		if self.ws:
			self.ws.stop()
			self.refreshUi(error=Exception("Connection aborted"))
		self.updating = False
		self.sending = False
		self.downloading = False
		self.uploading = False
		self.verifying = False
	
	
	# The Chat/Websocket RPC uses it's own threading mechanism,
	# we have to wrap to be QT-safe.
	# Theese callbacks are called from the background worker thread,
	# so it's unsafe to update the UI.
	def push_ws_update(self, frame, ws):
		self.wsUpdate.emit(frame)
	def push_ws_connect(self, ws):
		self.wsConnect.emit(1)
	def push_ws_disconnect(self, ws):
		self.wsDisconnect.emit(1)
	# So we use signals
	wsUpdate = QtCore.pyqtSignal(object)
	wsConnect = QtCore.pyqtSignal(int)
	wsDisconnect = QtCore.pyqtSignal(int)
	def setup_ws_signals(self):
		self.wsUpdate.connect(self.on_ws_update)
		self.wsConnect.connect(self.on_ws_connect)
		self.wsDisconnect.connect(self.on_ws_disconnect)
	
	def on_ws_connect(self):
		self.resync()
		self.refreshUi()
	
	def on_ws_disconnect(self):
		self.refreshUi()
	

	def tab_switched(self, i):
		tab = self.ui.tabWidget.widget(i)
		mw = self.iso.mainwin
		self.setTabBold(tab, False)
		name = self.getTabTitle(tab)
		icon = self.getTabIcon(tab)
		if not name:
			return
		if name.startswith("BTS"):
			name = name[0:8]+"..."+name[12:]
		mw.setTabTitle(self, name)
		mw.setTabIcon(self, icon)

	def getMemoKey(self, account_name):
		account = self.iso.getAccount(account_name)
		memo_key = account["options"]["memo_key"]
		return memo_key

	def keyFromLabel(self, label, force_local=False):
		if label.startswith("BTS"):
			self.known_expansions[label] = label, "key", "label"
			return label, "key", label
		# local blind account?
		blind = self.iso.store.blindAccountStorage.getByLabel(label)
		if blind:
			tag = "blind_contact" if blind["keys"] else "blind_contact"
			self.known_expansions[key] = blind["pub"], tag, blind["label"]
			return blind["pub"], tag, blind["label"]
		# bitshares accont?
		account = self.iso.getAccount(label)
		memo_key = account["options"]["memo_key"]
		tag = "contact"
		if not("keys" in account):
			account["keys"] = self.iso.store.countPrivateKeys([memo_key])
		tag = "account" if account["keys"] else "contact"
		self.known_expansions[memo_key] = memo_key, tag, account["name"]
		return memo_key, tag, account["name"]

	def keyExpandLabel(self, key, force_local=False):
		if not key.startswith("BTS"):
			return self.keyFromLabel(key)
		
		if key in self.known_expansions:
			return self.known_expansions[key]
		
		# local blind account?
		blind = self.iso.store.blindAccountStorage.getByPublicKey(key)
		if blind:
			tag = "blind_contact" if blind["keys"] else "blind_contact"
			self.known_expansions[key] = blind["pub"], tag, blind["label"]
			return blind["pub"], tag, blind["label"]
		# chat room?
		room = self.iso.store.chatroomStorage.getBy(pub=key)
		if room:
			tag = "room"
			self.known_expansions[key] = room["pub"], tag, key
			return room["pub"], tag, key
		account = None
		try:
			account = self.iso.getAccount(key, force_local=force_local)
		except Exception as e:
			try:
				accname = self.iso.bts.wallet.getAccountFromPublicKey(key)
				account = self.getAccount(accname, force_local=force_local)
			except:
				pass
		if account:
			if not("keys" in account):
				account["keys"] = self.iso.store.countPrivateKeys([key])
			tag = "account" if account["keys"] else "contact"
			self.known_expansions[key] = key, tag, account["name"]
			return key, tag, account["name"]
		
		return self.keyFromLabel(key)

	def sync_messages(self):
		self.chat_delay -= self.chat_delay_interval
		if not self.initialized and not self.retry_init:
			return
		if self.ws and self.ws.connected: # If we're using WS rpc, do nothing
			self.start_sender()
#			if not(len(self.roomkeys)): # but if there are rooms, check em
#				self.start_reader()
#				return
		if self.chat_delay <= 0 or (self.must_resync and not self.retry_init):
			if self.updating: # DO NOTHING
				return
			if self.ws and self.ws.connected:
				if len(self.roomkeys):
					self.start_reader(roomonly=True)
			else:
				self.resync()
			self.must_resync = False
			self.chat_delay = self.chat_delay_base

	def on_popid(self, msgid):
		if not(msgid in self.messages):
			return False
		messages.pop(msgid, None)

		tab = self.getmakeTab(msg["memo"]["from"], msg["memo"]["to"])
		tab.on_popid(msgid)

		return True

	def on_message(self, msg):
		self.decodeMessage(msg)
		self.autoAcceptBlind(msg)
		ch = False
		if msg["id"] in self.messages:
			omsg = self.messages[msg["id"]]
			if not(omsg["read"] is None) and omsg["read"] >= 1:
				if msg["read"] is None or msg["read"] == 0:
					msg["read"] = omsg["read"] # do not downgrade
			for k in ['read','sent','time','expires']:
				if msg[k] != omsg[k]:
					ch = True
		else:
			if msg["id"] in self.over_read:
				msg["read"] = self.over_read.pop(msg["id"])
			ch = True
		self.storeMessage(msg)
		self.on_readstatus(msg, msg["read"])
		self.needRedraw = ch

		tab = self.getmakeTab(msg["memo"]["from"], msg["memo"]["to"])
		mch = tab.on_message(msg, ch)
		if mch:
			if self.ui.tabWidget.currentWidget() != tab:
				self.setTabBold(tab, True)

		return ch

	def on_readstatus(self, msg, r):
		if r is None:
			if msg["sent"] == 0:
				return # ignore invalid status
		if r == 0:
			if msg["memo"]["from"] == str(self.from_pub):
				self.verify_queues.add(msg["memo"]["from"], msg["id"])
		else:
			self.verify_queues.remove(msg["memo"]["from"], msg["id"])
		
		ch = bool(msg["read"] != r)
		self.messages[msg["id"]]["read"] = r
		self.needRedraw = ch

		tab = self.getmakeTab(msg["memo"]["from"], msg["memo"]["to"])
		tab.on_readstatus(msg, r, ch)

		return ch

	def on_ws_update(self, frame):
		mode = list(frame["update"].keys())[0]
		data = frame["update"][mode]
		changed = False

		if mode == "message":
			msg = data
			ch = self.on_message(msg)
			if ch:
				changed = True

		if mode == "read":
			msgid, read = data
			if not msgid in self.messages:
				self.over_read[msgid] = read
				return
			msg = self.messages[msgid]
			ch = self.on_readstatus(msg, read)
			if ch:
				changed = True

		if changed:
			self.redrawMessages()

	def autoAcceptBlind(self, msg):
		if not 'message' in msg: return
		if "_autoblind" in msg: return
		wallet = self.iso.bts.wallet
		url = msg['message']
		try:
			if not(url.startswith("bitshares:blind_receipt/")):
				return
			o = parseBTSUrl(url)
			receipt = o['action'][1]
			data = o['params']
			if not receipt: return
			comment1 = o['params'].get("comment", "")
			comment2 = ""
			ok = False
			try:
				ok, _, _ = receive_blind_transfer(
					wallet, receipt, comment1, comment2)
			except Exception as error:
				self.log_error("Failed to auto-accept blind transfer %s: %s", receipt, str(error))
				log.error("Failed to auto-accept blind transfer %s: %s", receipt, str(error))
			if ok:
				self.log.info("Auto-accepted blind transfer %s", receipt)
				log.info("Auto-accepted blind transfer %s", receipt)
		except Exception as error:
			return
		finally:
			msg["_autoblind"] = 1

	def resync(self):
		if self.retry_init and not(self.initializing):
			self.start_init()
		if not self.initialized:
			return
		if self.ws:
			self.ws.start()
		self.start_sender()
		self.start_reader()
		self.start_verifier()
		self.must_resync = False

	def start_sender(self):
		if not self.initialized:
			return
		rpc = self.pick_rpc()
		if self.sending == rpc:
			return
		if self.send_queue.empty():
			return
		self.sending = rpc # True
		self.sender_.fetch(self.sendMessages_before, rpc,
			ready_callback=self.sendMessages_after,
			error_callback=self.sendMessages_error,
			ping_callback=self.sendMessages_ping,
		)

	def sendMessages_ping(self, uid, ps, data):
		if ps == -2: # cancelled
			self.sending = False
			self.refreshUi()
		
		if ps == 60: # popid
			self.on_popid(data)
		
		if ps == 70: # message sent
			self.on_message(data)

	def sendMessages_before(self, rpc, request_handler=None):
		rh = request_handler
		
		while not(rh.cancelled):
			try:
				msg = self.send_queue.get(block=False)#block=block, timeout=timeout)
			except queue.Empty:
				break
			old_id = msg["id"]
			try:
				msg = rpc.post_memo(msg['memo'])
				self.decodeMessage(msg)
				msg["sent"] = 1
				self.verify_queues.add(msg['memo']['from'], msg['id'])
			except:
				self.send_queue.put(msg, block=False)
				raise
			popid = None
			if old_id != msg["id"]:
				rh.ping(60, old_id) # pop id
			
			rh.ping(70, msg) # message sent
	
	def sendMessages_after(self, uid, args):
		self.sending = False
		self.redrawMessages()
		self.refreshUi()
	
	def sendMessages_error(self, uid, error):
		self.sending = False
		self.redrawMessages()
		self.refreshUi(error=error)
	

	def start_verifier(self):
		rpc = self.pick_rpc()
		if self.verifying == rpc:
			return
		t = 0
		for k in self.verify_queues:
			t = len(self.verify_queues[k])
		if t == 0:
			return
		self.verifying = rpc # True
		self.verifier.fetch(self.verifyMessages_before, rpc,
			ready_callback=self.verifyMessages_after,
			error_callback=self.verifyMessages_error,
			ping_callback=self.verifyMessages_ping,
		)

#	def _bg_wait(self, rh, timeout=5):
#		while not rh.cancelled:
#			print("WAIT", timeout)
#			if timeout <= 0: break
#			timeout -= 0.1
#			time.sleep(0.1)
#		print("WAIT OVER")

	def verifyMessages_ping(self, uid, ps, data):
		if ps == 50:
			msgid, r = data
			msg = self.messages[msgid]
			ch = self.on_readstatus(msg, r)

	def verifyMessages_before(self, rpc, request_handler=None):
		rh = request_handler
#		timeout = 5
#		postout = 15
#		while self.sending or not(self.send_queue.empty()):
#			if rh.cancelled: break
#			if timeout <=0: break
#			timeout -= 0.1
#			time.sleep(0.1)
#			postout = 12.5
#		self._bg_wait(rh, postout)
		for pubkey in self.verify_queues:
			if rh.cancelled: break
			ids = list(self.verify_queues[pubkey])
			results = rpc.verifyMessages(ids, pubkey=pubkey)
			for i, res in enumerate(results):
				if rh.cancelled: break
				rh.ping(50, [ ids[i], res ])
	
	def verifyMessages_after(self, uid, args):
		self.verifying = False
		self.redrawMessages()
		self.refreshUi()

	def verifyMessages_error(self, uid, error):
		self.verifying = False
		self.redrawMessages()
		self.refreshUi(error=error)

	def pick_rpc(self):
		return self.ws if (self.ws and self.ws.connected) else self.rpc

	def start_reader(self, roomonly=False):
#		if not self.initialized:
#			return
		rpc = self.pick_rpc()
		if self.updating == rpc:
			return
		self.updating = rpc # True
		self.updater.fetch(self.readMessages_before, rpc, roomonly,
			ready_callback=self.readMessages_after,
			error_callback=self.readMessages_error,
			ping_callback=self.readMessages_ping,
		)

	def readMessages_ping(self, uid, ps, msg):
		if ps == -2:
			if self.updating:
				rpc = self.updating
				rpc.last_msg_id = self._preserve_lastmsgid
			self.updating = False
			self.must_refresh = True
		
		if ps == 80: # message recvd
			self.on_message(msg)

	def readMessages_before(self, rpc, roomonly, request_handler=None):
		rh = request_handler
		
		new_motd = None
		if self.motd is None:
			new_motd = self.getMotd()
		
		room_pubs = list(self.roomkeys.keys())
		self._preserve_lastmsgid = dict(rpc.last_msg_id)
		new_msgs = rpc.getMessages(decode=False, pubkeys=room_pubs)
		for msg in new_msgs:
			self.decodeMessage(msg)
			msg["sent"] = 1
			rh.ping(80, msg) # message recvd
		
		all_keys = list(rpc.privkeys.keys())
		for rp in room_pubs:
			if rp in all_keys:
				all_keys.remove(rp)
		
		if roomonly:
			return (new_motd,) # do not check for non-room messages
		
		new_msgs = rpc.getMessages(decode=False, pubkeys=all_keys)
		for msg in new_msgs:
			self.decodeMessage(msg)
			msg["sent"] = 1
			rh.ping(80, msg) # message recvd
		
		return (new_motd,)

	def readMessages_after(self, uid, args):
		(new_motd,) = args
		if new_motd:
			self.add_log_record(new_motd)
		self.updating = False
		self.redrawMessages()
		self.refreshUi()

	def readMessages_error(self, uid, error):
		rpc = self.updating
		rpc.last_msg_id = self._preserve_lastmsgid
		self.updating = False
		self.redrawMessages()
		self.refreshUi(error=error)

	def anchor_click(self, a):
		url = a.url()
		t, id = url.split(":")
		if t == "download":
			self.download_file_message(id)
		elif t == "save":
			self.save_inline_file(id)

	def save_inline_file(self, id):
		path, _ = QtGui.QFileDialog.getSaveFileName(self, 'Save inline file', '', "any file (*.*)")
		if not path:
			return False

		msg = self.messages[id]
		b, ct = parseMessage(msg["message"])
		with open(path, "wb") as f:
			f.write(b)

	def upload_file(self, from_pub, to_pub, filename):
		if self.uploading:
			self.upload_queue.append((from_pub, to_pub, filename))
			return
		
		self.uploading = True
		self._up_filename = filename
		self.uploader.fetch(self.upload_file_bg, from_pub, to_pub, filename,
			ready_callback = self.upload_file_after,
			error_callback = self.upload_file_error,
			ping_callback  = self.upload_file_ping)
		self.refreshUi()

	def upload_file_bg(self, from_pub, to_pub, filename):
		msg = self.rpc.sendFile(to_pub, filename, from_pubkey=from_pub)
		self.decodeMessage(msg)
		return (msg, )

	def upload_file_after(self, uid, args):
		(msg, ) = args
		self.uploading = False
		
		msg["sent"] = 1
		self.on_message(msg)
		self.redrawMessages()
		self.refreshUi()
		
		if len(self.upload_queue):
			from_pub, to_pub, filename = self.upload_queue.pop()
			self.upload_file(from_pub, to_pub, filename)

	def upload_file_error(self, uid, error):
		self.uploading = False
		self.upload_queue.append(self._up_filename)
		showexc(error)
		self.refreshUi(error=error)

	def upload_file_ping(self, uid, ct, cd):
		if ct == -2: # CANCELLED!
			self.uploading = False
			self.refreshUi()
		self.ping_callback() #uid, ct, cd)

	def download_file_message(self, msgid, path=None):
		msg = self.messages[msgid]
		meta, _ = parseMessage(msg["meta_data"])
		filename = meta["filename"]
		
		if not path:
			path, _ = QtGui.QFileDialog.getSaveFileName(self,
			'Save file', filename, "any file (*.*)")
		if not path:
			return False
		
		if self.downloading:
			msg["downloading"] = 1
			self.download_queue.append((msgid,path))
			self.redrawMessages()
			return
		
		msg["downloading"] = 2
		msg["downloaded"] = 0
		self._down_msgid = msgid
		self.redrawMessages()
		
		self.downloading = True
		self.downloader.fetch(self.download_file, msg, path,
			ready_callback = self.download_file_after,
			error_callback = self.download_file_error,
			ping_callback  = self.download_file_ping)
		self.refreshUi()

	def download_file(self, msg, filename):
		self.rpc.acceptFile(msg, filename)
		return (msg, )

	def download_file_ping(self, uid, ct, cd):
		if ct == -2: # CANCELLED!
			self.downloading = False
			self.refreshUi()
		self.ping_callback()#uid, ct, cd)

	def download_file_after(self, uid, args):
		self.downloading = False
		(msg, ) = args
		
		self.messages[msg["id"]]["downloaded"] = 1
		self.messages[msg["id"]]["downloading"] = 0
		
		if len(self.download_queue):
			msgid,path = self.download_queue.pop()
			self.download_file_message(msgid, path)
		else:
			self.redrawMessages()
			self.refreshUi()

	def download_file_error(self, uid, error):
		self.downloading = False
		msgid = self._down_msgid
		self.messages[msgid]["downloaded"] = 0
		self.messages[msgid]["downloading"] = 0
		self.redrawMessages()
		self.refreshUi()


	def storeMessage(self, msg):
		time_changed = False
		old_msg = self.messages.get(msg["id"], None)
		if old_msg:
			if msg["time"] != old_msg["time"]:
				time_changed = True
		elif len(self.messages):
			last_msg = self.messages[ next(reversed(self.messages)) ]
			if msg["time"] < last_msg["time"]:
				time_changed = True
		
		self.messages[msg["id"]] = msg
		if time_changed:
			self.reorderMessages()

	def reorderMessages(self):
		self.messages = od(sorted(self.messages.items(),
				key=lambda m: m[1]['time'], reverse=False))

	def redrawMessages(self):
		for i in range(1, self.ui.tabWidget.count()):
			tab = self.ui.tabWidget.widget(i)
			tab.redrawMessages()
		return

	def queueMessage(self, to_pub, text):
		msg = { }
		msg["memo"] = self.rpc.encodeMemo(self.from_pub, to_pub, text)
		msg["message"] = text
		msg["meta"] = None
		
		msg["id"] = self.rpc.hashMessage(msg['memo'])
		
		msg["expires"] = 0
		msg["time"] = datetime.datetime.utcnow().timestamp()
		msg["sent"] = 0
		msg["read"] = 0
		
		self.send_queue.put( msg )
		
		self.on_message(msg)
		self.redrawMessages()
		self.must_resync = True
		self.start_sender()

	def queueInlineFile(self, from_pub, to_pub, filename):
		clearbody, ct, size = fileToDataURI(filename)
		return self.queueMessage(to_pub, clearbody)

	def queueFile(self, from_pub, to_pub, filename):
		self.upload_file(from_pub, to_pub, filename)

	def file_dropped(self, links):
		i = self.ui.tabWidget.currentIndex()
		if i < 1:
			return False
		tab = self.ui.tabWidget.widget(i)
		for l in links:
			if not os.path.isfile(l):
				continue
			self.attachFile(tab.from_pub, tab.to_pub, l)

	def getMotd(self):
		if self.motd is None:
			self.motd = self.rpc.motd()
		return self.motd

	def getConfig(self):
		if self.config is None:
			self.config = self.rpc.status(self.from_pub)
		return self.config

	@safeslot
	def attachFile(self, from_pub, to_pub, path):
		config = self.getConfig()
		stats = os.stat(path)
		filesize = stats.st_size
		if filesize * 2.2 < config['max_message_size']:
			self.queueInlineFile(from_pub, to_pub, path)
		elif filesize * 2.2 < config['max_file_size']:
			self.queueFile(from_pub, to_pub, path)
		else:
			showexc("File too large %d > max_file_size %d" % (filesize, config['max_file_size']))
			return
	

	def decodeMessage(self, msg):
		if "_decoded" in msg:
			return msg
		memo = msg["memo"]
		if memo["message"]:
			try:
				msg["message"] = self.rpc.decodeMemo(**memo)
			except:
				pass
		if msg["meta"]:
			try:
				meta = msg["meta"]
				meta['from'] = memo['from']
				meta['to'] = memo['to']
				msg["meta_data"] = self.rpc.decodeMemo(**meta)
			except:
				pass
		for k in ["sent", "downloading", "downloaded"]:
			if not k in msg:
				msg[k] = 0
		msg["_decoded"] = 1
		return msg

	def refreshUi(self, error=None):
		icons = {
			"error": ":/icons/images/red.png",
			"syncing": ":/op/images/op/fill_order.png",
			"connecting": ":/icons/images/yellow.png",
			"online": ":/icons/images/green.png",
		}
		if error:
			ico = "error"
			self.log_error(str(error))
		elif (self.updating or self.sending or self.verifying
			or self.uploading or self.downloading):
			ico = "syncing"
		elif self.ws and self.ws.connected:
			ico = "online"
		else:
			ico = "connecting"
		icon = picon(icons[ico])
		
		self.ui.networkStatus.setPixmap(icon)
		for i in range(1, self.ui.tabWidget.count()):
			tab = self.ui.tabWidget.widget(i)
			tab.refreshUi_icon(icon)#:networkStatus.setPixmap(icon)
	
	def _getTabHeader(self, tab):
		tw = self.ui.tabWidget
		tb = tw.tabBar()

		i = tw.indexOf(tab)
		old = tb.tabButton(i, QtGui.QTabBar.LeftSide)
		if old:
			lbl1 = old.layout().itemAt(0).widget()
			lbl2 = old.layout().itemAt(1).widget()
			return lbl1, lbl2

		lbl1 = QtWidgets.QLabel()
		lbl2 = QtWidgets.QLabel()

		lbl1.setMaximumSize(QtCore.QSize(24, 24))

		lay = QtWidgets.QHBoxLayout()
		lay.addWidget(lbl1)
		lay.addWidget(lbl2)

		lay.setSpacing(0)
		lay.setContentsMargins(0,0,0,0)

		box = QtWidgets.QWidget()
		box.setLayout(lay)
		tb.setTabButton(i, QtGui.QTabBar.LeftSide, box)
		
#		sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
#		sizePolicy.setHorizontalStretch(1)
#		sizePolicy.setVerticalStretch(0)
#		sizePolicy.setHeightForWidth(box.sizePolicy().hasHeightForWidth())
#		box.setSizePolicy(sizePolicy)
		
		box.setMinimumSize(QtCore.QSize(150, 0))
		box.setMaximumSize(QtCore.QSize(200, 20))
		
		return lbl1, lbl2

	def getTabTitle(self, tab):
		if not(hasattr(tab, '_title_')):
			return ''
		return tab._title_

	def getTabIcon(self, tab):
		if not(hasattr(tab, '_icon_')):
			return ''
		return tab._icon_

	def setTabTitle(self, tab, title):
		lbl1, lbl2 = self._getTabHeader(tab)
		lbl2.setText(title)
		tab._title_ = title

	tabIcons ={
		"server": ":/icons/images/messages.png",
		"room": ":/icons/images/house.png",
		"account": ":/op/images/op/account_update_key.png",
		"contact": ":/icons/images/account.png",
		"blind_account": ":/icons/images/account_suit.png",
		"blind_contact": ":/op/images/op/blind_transfer.png",
		"key": ":/icons/images/key.png",
	}

	def setTabIcon(self, tab, icon):
		lbl1, lbl2 = self._getTabHeader(tab)
		icons = self.tabIcons
		lbl1.setPixmap(picon(icons[icon]))
		tab._icon_ = icons[icon]
		return icons[icon]

	def setTabBold(self, tab, bold=True):
		lbl1, lbl2 = self._getTabHeader(tab)
		lbl2.setStyleSheet("font-weight: bold;" if bold else "")

	def add_log_record(self, msg):
		with ScrollKeeper(self.ui.serverLog, cursor=True):
			ce = self.ui.serverLog
			tc = ce.textCursor()
			tc.movePosition(QTextCursor.End)
			tc.insertText(msg+"\n")
			ce.setTextCursor(tc)
	def log_info(self, msg, *args):
		self.add_log_record(msg % args)
	def log_error(self, msg, *args):
		self.add_log_record(msg % args)
