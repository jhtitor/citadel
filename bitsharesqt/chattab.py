# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui, QtWidgets
from uidef.chattab import Ui_ChatTab
_translate = QtCore.QCoreApplication.translate

from rpcs.bitshareschat._http import BitSharesChatHTTP
from rpcs.bitshareschat._websocket import BitSharesChatWS
from rpcs.bitshareschat.filedata import parseMessage
from rpcs.bitshareschat.filedata import fileToDataURI
from rpcs.bitshareschat._websocket import MutexSet
from collections import OrderedDict as od
import queue

#from PyQt5.QtGui import QTextCursor

from .netloc import RemoteFetch
from .utils import *
import json
import datetime

import logging
log = logging.getLogger(__name__)

import os
import time



try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class ChatTab(QtWidgets.QWidget):
	
	def __init__(self, *args, **kwargs):
		self.ping_callback = kwargs.pop("ping_callback", None)
		self.iso = kwargs.pop("isolator", None)
		self.ptab = kwargs.pop("parentobj", None)
		super(ChatTab, self).__init__(*args, **kwargs)
		self.ui = Ui_ChatTab()
		self.ui.setupUi(self)
		
		self._index = 6
		
		mw = self.iso.mainwin
		
		self.messages = od() # list of all messages
		
#		self.connect(self, QtCore.SIGNAL("dropped"), self.file_dropped)
		
		self.needRedraw = True
		
		self.ui.attachButton.clicked.connect(self.select_file)
		self.ui.lineEdit.returnPressed.connect(self.enter_press)
		self.ui.chatLog.anchorClicked.connect(self.anchor_click)
		self.ui.detailsToggle.clicked.connect(self.toggle_details)
		self.ui.detailsFrame.setVisible(False)
#		self.ui.closeButton.clicked.connect(self.close_tab)
#		self.ui.deleteAllButton.clicked.connect(self.delete_all_messages)
		self.ui.closeButton.setVisible(False)
		self.ui.deleteAllButton.setVisible(False)


#		self.toggle_details()
		
		self.isRoom = False
		self.setted_up = False

	def setupRoom(self, from_key_or_label, room_brain_key):
#		if self.setted_up:
#			return
#		self.setted_up = True
		self.isRoom = True

		from bitsharesbase.account import BrainKey
		room_bk = BrainKey(room_brain_key)
		to_priv = room_bk.get_blind_private()

		from_key, from_icon, from_label = self.keyExpandLabel(from_key_or_label)
		to_key, to_icon, to_label = str(to_priv.pubkey), "room", room_brain_key
		
		self._title_ = to_label
		self.ptab.setTabTitle(self, to_label)
		self._icon_ = self.ptab.setTabIcon(self, to_icon)
		
		self.from_pub = from_key
		self.to_pub = to_key
		
		self.roompriv = to_priv
		self.roompub = str(to_priv.pubkey)
		
		icons = self.ptab.tabIcons
		self.ui.toIcon.setPixmap(picon(icons[to_icon]))
		self.ui.toName.setText(to_label)
		self.ui.toPub.setText(to_key)

	def setupConnection(self, from_key_or_label, to_key_or_label):#, server_url):
		if self.setted_up:
			return
		self.setted_up = True
		from_key, from_icon, from_label = self.keyExpandLabel(from_key_or_label)
		to_key, to_icon, to_label = self.keyExpandLabel(to_key_or_label)

		self._title_ = to_label
		self.ptab.setTabTitle(self, to_label)
		self._icon_ = self.ptab.setTabIcon(self, to_icon)

		#print("SETUP CONNECTION <", str(from_key))
		#priv_key = self.iso.getPrivateKeyForPublicKeys([from_key])[0]
		
		self.from_pub = from_key
		self.to_pub = to_key
		
		icons = self.ptab.tabIcons
		self.ui.fromIcon.setPixmap(picon(icons[from_icon]))
		self.ui.fromName.setText(from_label)
		self.ui.toIcon.setPixmap(picon(icons[to_icon]))
		self.ui.toName.setText(to_label)
		self.ui.fromPub.setText(from_key)
		self.ui.toPub.setText(to_key)
		
#		self.ui.chatServer.setText(server_url)
		
#		mw = self.iso.mainwin
#		mw.setTabTitle(self, to_label)
		
#		self.refreshUi()
	
	def close(self): # gets called on tab destruction
		pass
	
	
	def keyExpandLabel(self, key):
		return self.ptab.keyExpandLabel(key)

	def keyFromLabel(self, label):
		return self.ptab.keyFromLabel(label)

	def toggle_details(self):
		with ScrollKeeper(self.ui.chatLog):
			v = self.ui.detailsFrame.isVisible()
			self.ui.detailsFrame.setVisible(not(v))

	def on_popid(self, msgid):
		if not(msgid in self.messages):
			return False
		messages.pop(msgid, None)
		return True

	def on_message(self, msg, fch=None):
		self.ptab.decodeMessage(msg)
		ch = False
		if msg["id"] in self.messages:
			omsg = self.messages[msg["id"]]
			for k in ['read','sent','time']:
				if msg[k] != omsg[k]:
					ch = True
		else:
			ch = True
		if not ch and fch: ch = True
		self.storeMessage(msg)
		self.on_readstatus(msg, msg["read"])
		self.needRedraw = ch or self.needRedraw
		return ch

	def on_readstatus(self, msg, r, fch=None):
		if not msg["id"] in self.messages:
			# This can happen due to races in on_message/on_readstatus
			# pings. It's ok, though, if on_message is late,
			# it contains a more-up-to-date version of this field.
			#print(msg["id"], r, "ignored")
			return False
		ch = bool(msg["read"] != r)
		if not ch and fch: ch = True
		self.messages[msg["id"]]["read"] = r
		self.needRedraw = ch or self.needRedraw


		return ch

	@safeslot
	def anchor_click(self, a):
		url = a.url()
		t, id = url.split(":", 1)
		if t == "download":
			self.ptab.download_file_message(id)
		elif t == "save":
			self.ptab.save_inline_file(id)
		elif t == "bitshares":
			self.iso.mainwin.openBTSUrl(url)
		elif t == "bs2chat":
			self.iso.mainwin.openBTSChatUrl(url)


	def htmlLinks(self, s):
		import re
		pos = re.findall("([a-z0-9]+):(.+?)($|\s|\"|\')", s)
		for (scheme, path, end) in pos:
			if scheme in [ "download", "save" ]:
				continue
			full = scheme + ":" + path
			note = scheme.upper() + " link"
			r = "<a title='{}' href='{}'>{}</a>".format(
				note, full, full
				)
			s = s.replace(full, r)
		return s

	def metaAsHTML(self, meta):
		h = ''
		special = ['filename', 'content-length', 'content-type']
		ct = meta.get('content-type', "")
		if "filename" in meta:
			h += "file <b>{}</b><br/>".format(meta["filename"])
		if "content-length" in meta:
			h += "<font color='#333333'>{}</font> {}<br/>".format(
				neatbytes(meta["content-length"]), ct)
		for k, v in meta.items():
			if k in special:
				continue
			h += "{}: <span>{}</span><br/>".format(k, v)
		return h

	def msgAsHTML(self, msg):
		align="center"
		color="white"
		ml = "0"
		mr = "0"
		if self.from_pub == msg["memo"]["to"]:
			align = "left"
			color = "#cb99a2"
			mr = "60px"
		if self.from_pub == msg["memo"]["from"]:
			align = "right"
			color ="#82feff"
			ml = "60px"
		muc = (self.isRoom and align == "center")
		if muc:
			align="left"
			color = "#cb99a2"
			mr = "60px"
		style = "background-color: {}; border: 1px solid #eeeeee; padding: 10px; margin-bottom: 10px; margin-left: {}; margin-right: {};".format(color, ml, mr)
		h = "<div id='{}' align='{}' style='{}'>".format(msg['id'], align, style)
		if muc:
			alias = msg["memo"]["from"]
			if not "_alias" in msg:
				k, i, l = self.keyExpandLabel(msg["memo"]["from"])
				msg["_alias"] = l
				msg["_alias_icon"] = i
			h += "<img src='{}'/>".format(self.ptab.tabIcons[msg["_alias_icon"]])
			h += "<i>{}</i>: &nbsp; ".format(msg["_alias"])
		if 'message' in msg:
			embed = False
			ct = "text/plain"
			try:
				data, ct = parseMessage(msg["message"])
				embed = True
			except:
				pass
			if ct.startswith("image/"):
				h += "<img src='{}'/><br/>".format(msg["message"])
			if ct == "text/plain":
				txt = msg["message"]
				txt = txt.replace("<", "&lt;")
				txt = txt.replace(">", "&gt;")
				txt = self.htmlLinks(txt)
				h += "<span>" + txt + "</span>"
			elif embed:
				h += "<i>inline file</i><br/>".format(ct)
				h += self.metaAsHTML({
					"content-type": ct,
					"content-length": len(data),
				})
				h += "<a href='save:{}'><img src=':/icons/images/download'/></a>".format(msg["id"])
		if 'meta_data' in msg and msg['meta_data']:
			meta, _ = parseMessage(msg["meta_data"])
			thumbnail = meta.pop("thumbnail", None)
			if thumbnail:
				h += "<img src='{}'/><br/>".format(thumbnail)
			#h += "<ul style='margin-top: 0; background-color: {}'>".format(color)
			
			h += self.metaAsHTML(meta)
			h += "<a href='download:{}'><img src=':/icons/images/download'/></a>".format(msg["id"])
			if msg["downloading"]:
				h += "<small>downloading...</small>"
			#h += "</ul>"
		if msg['sent'] == 0:
			icon = "<img src=':/icons/images/yellow.png'/>"
		elif msg['read'] is None:
			icon = "<img src=':/icons/images/crossout.png'/>"
		elif msg['read'] >= 1:
			icon = "<img src=':/icons/images/tick.png'/>"
		else:
			icon = "<img src=':/icons/images/wait.png'/>"
		if self.isRoom:
			if msg['sent'] == 0:
				icon = "<img src=':/icons/images/yellow.png'/>"
			else:
				icon = ""

		if align == "left":
			icon = ""
		h += icon
		h += "</div>\n"
		return h

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
#		if time_changed:
		self.reorderMessages()

	def reorderMessages(self):
		self.messages = od(sorted(self.messages.items(),
				key=lambda m: m[1]['time'], reverse=False))

	def redrawMessages(self):
		if self.needRedraw == False: return
		self.needRedraw = False
#		tc = self.ui.chatLog.textCursor()
#		tc.setPosition(startPos)
#		tc.setPosition(endPos, QTextCursor.KeepAnchor)
		
		hh = ""
		for id, msg in self.messages.items():
			hh += self.msgAsHTML(msg)

		with ScrollKeeper(self.ui.chatLog):
			self.ui.chatLog.setHtml(hh)

#		self.ui.chatLog.setTextCursor(tc)

	def enter_press(self):
		text = str(self.ui.lineEdit.text())
		self.ptab.queueMessage(self.to_pub, text)
		self.ui.lineEdit.setText("")
	
	def select_file(self):
		path, _ = QtGui.QFileDialog.getOpenFileName(self, 'Send file', '', "any file (*.*)")
		if not path:
			return False
		self.ptab.attachFile(self.from_pub, self.to_pub, path)

	def refreshUi(self):
		pass

	def refreshUi_icon(self, icon):
		self.ui.networkStatus.setPixmap(icon)
