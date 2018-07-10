from PyQt5 import QtGui, QtCore

COLOR_GREEN = "#27ca41"
COLOR_RED = "#e44842"

def ignore_hidpi_settings():
    font = app().font()
    font.setPixelSize(12)
    app().setFont(font)

from pytimeparse.timeparse import timeparse
def deltasec(tp, default=3600*24):
	if not tp or len(tp) < 1:
		return default
	return timeparse(tp)
def deltainterval(s):
	edges = [ ("s", 1), ("m", 60), ("h", 60), (" day", 24),
		(" week", 7), (" month", 4), (" year", 12),]
	unit = "s"
	for remark, div in edges:
		n = s / div
		if n < 1:
			break
		s = n ; unit = remark
	suf = "s" if (s > 1 and len(unit) > 1) else ""
	return "%0.f%s%s" % (s, unit, suf)

def generate_webwalletlike_password():
	from bitsharesbase.account import PrivateKey
	random_private_key_asWif = repr(PrivateKey(wif=None))
	return ("P" + random_private_key_asWif) [0:45]

def app():
	return QtGui.QApplication.instance()

def qclip(text=None):
	clipboard = QtGui.QApplication.clipboard()
	if text is None: # get
		return clipboard.text()
	else: # set
		clipboard.setText(text)

def anyvalvis(widget, default):
	if widget.isVisible():
		return any_value(widget)
	return default

def any_value(widget):
	if isinstance(widget, QtGui.QComboBox):
		return widget.currentText()
	if isinstance(widget, QtGui.QLineEdit):
		return widget.text()
	if isinstance(widget, QtGui.QSpinBox):
		return widget.value()
	if isinstance(widget, QtGui.QDoubleSpinBox):
		return widget.value()

def any_change(widget, func):
	if isinstance(widget, QtGui.QComboBox):
		return on_combo(widget, func)
	if isinstance(widget, QtGui.QLineEdit):
		return on_edit(widget, func)
	if isinstance(widget, QtGui.QSpinBox):
		return on_spin(widget, func)
	if isinstance(widget, QtGui.QDoubleSpinBox):
		return on_spin(widget, func)

import traceback
def showexc(e, echo=False):
	if echo or True:
		traceback.print_exc()
	showerror(e.__class__.__name__ + ' | ' + str(e), additional=e.__class__.__doc__);


def showerror(message, title="Error", additional=None, details=None):
	msg = QtGui.QMessageBox()
	msg.setIcon( QtGui.QMessageBox.Critical )

	msg.setText(message)
	msg.setWindowTitle(title)
	msg.setWindowIcon(app().mainwin.windowIcon())

	if additional:
		msg.setInformativeText(str(additional))

	if details:
		msg.setDetailedText(details)

	msg.setStandardButtons( QtGui.QMessageBox.Ok )# |  QtGui.QMessageBox.Cancel)
	#msg.buttonClicked.connect(msgbtn)

	retval = msg.exec_()
	#print("value of pressed message box button:", retval)
	return retval


def showdialog(message, title="Information", additional=None, details=None, min_width=None, icon=None):
	msg = QtGui.QMessageBox()
	msg.setIcon( QtGui.QMessageBox.Information )
	
	msg.setText(message)
	msg.setWindowTitle(title)
	msg.setWindowIcon(app().mainwin.windowIcon())
	
	if min_width:
		msg.setStyleSheet("QLabel{min-width: "+str(min_width)+"px;}");
		msg.setIcon(QtGui.QMessageBox.NoIcon)
	
	if icon:
		msg.setIconPixmap(QtGui.QPixmap(icon));

	if additional:
		msg.setInformativeText(str(additional))
	
	if details:
		msg.setDetailedText(details)
	
	msg.setStandardButtons( QtGui.QMessageBox.Ok )# |  QtGui.QMessageBox.Cancel)
	#msg.buttonClicked.connect(msgbtn)
	
	retval = msg.exec_()
	#print("value of pressed message box button:", retval)
	return retval

# Aliases:
def showmessage(*args, **kwargs):
	return showdialog(*args, **kwargs)
def showmsg(*args, **kwargs):
	return showdialog(*args, **kwargs)

def askyesno(message):
	mb = QtGui.QMessageBox
	if mb.question(None, '', message,
		mb.Yes | mb.No, mb.No) == mb.Yes:
		return True
	return False

def qmenu(elem, func):
	elem.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
	elem.customContextMenuRequested.connect(func)

def qmenu_exec(elem, menu, position):
	return menu.exec_(elem.viewport().mapToGlobal(position))

def qaction(qttr, menu, text, func):
	act = QtGui.QAction(qttr.tr(text), menu)
	act.triggered.connect(func)
	#newAct->setShortcuts(QKeySequence::New);
	#newAct->setStatusTip(tr("Create a new file"));
	menu.addAction(act)
	return act

def qtimer(delay, cb):
	timer = QtCore.QTimer()
	timer.start(delay)
	timer.timeout.connect(cb)
	return timer

def licon(path):
	ico = QtGui.QPixmap(path)
	img = QtGui.QLabel("")
	img.setPixmap(ico)
	return img

def qicon(path):
	ico = QtGui.QPixmap(path)
	icon = QtGui.QIcon(ico)
	return icon
	img = QtGui.QLabel("")
	img.setPixmap(ico)
	return img


def fill_combo(combo, options):
	combo.clear()
	for option in options:
		combo.addItem(option)

def sync_combo(combo, options):
	for option in options:
		if combo.findText(option, QtCore.Qt.MatchFixedString) >= 0:
			continue
		combo.addItem(option)


def set_combo(combo, text, force=False):
	index = combo.findText(text, QtCore.Qt.MatchFixedString)
	if index >= 0:
		combo.setCurrentIndex(index)
	elif combo.lineEdit():
		combo.lineEdit().setText(text)
	elif force:
		combo.addItem(text)
		set_combo(combo, text, False)
	else:
		print("Unable to set", text, "on", combo)

def on_combo(combo, func):
	combo.editTextChanged.connect(func)
	combo.currentIndexChanged.connect(func)
def on_spin(spin, func):
	spin.valueChanged.connect(func)
def on_edit(line, func):
	line.textChanged.connect(func)


def set_itemflags(item, enabled=True, checked=False, checkable=False, selectable=True):
	o = 0
	if checked:
		checkable = True
	if selectable:
		o |= QtCore.Qt.ItemIsSelectable
	if enabled:
		o |= QtCore.Qt.ItemIsEnabled
	if checkable:
		o |= QtCore.Qt.ItemIsUserCheckable
	if checked:
		o |= QtCore.Qt.ItemIsChecked
	item.blockSignals(True)
	item.setFlags(o)
	item.blockSignals(False)

def table_selrow(table):
	indexes = table.selectionModel().selectedRows()
	if len(indexes) < 1:
		return -1
	j = indexes[0].row()
	return j

from PyQt5.QtWidgets import QTableWidgetItem
def set_col(table, row, col, val, fmt=None, color=None, align=None, editable=None, data=None):
	item = QTableWidgetItem(fmt % val if fmt else str(val))
	if color:
		item.setForeground(QtGui.QColor(color))
	if align=="right":
		item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
	if align=="center":
		item.setTextAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
	if not(editable is None):
		if editable:
			item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
				| QtCore.Qt.ItemIsEditable)
		else:
			item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
	if data:
		item.setData(99, data)
	
	table.setItem(row, col, item)
	return item


def stretch_table(table, col=None, hidehoriz=False):
	table.verticalHeader().hide()
	
	header = table.horizontalHeader()
	n = header.count()
	if col is None:
		col = n - 1
	for i in range(0, n):
		header.setResizeMode(i, QtGui.QHeaderView.ResizeToContents)
	if not(col is False):
		header.setResizeMode(col, QtGui.QHeaderView.Stretch)
	if hidehoriz:
		header.hide()

def stretch_tree(tree):
	header = tree.header()
	header.setResizeMode(0, QtGui.QHeaderView.ResizeToContents)
	#_treeWidget->header()->setStretchLastSection(false);
	#_treeWidget->header()->setSectionResizeMode(QHeaderView::ResizeToContents);
	#header.setResizeMode(1, QtGui.QHeaderView.Stretch)
	#table.verticalHeader().hide()

def merge_in(root, obj, key="", label=None, iso=None):
	
	item = QtGui.QTreeWidgetItem(root)
	
	item.setText(0, key)
	item.setText(1, str(obj))
	#print(obj, str(obj))
	if label:
		item.setText(1, label)
	
	nextlabel = None
	
	if type(obj) == str or type(obj) == int or type(obj) == float or type(obj) == bool:
		return
	elif type(obj) == dict:
		op_obj = obj
	elif type(obj) == list:
		pass
	elif obj is None:
		return
	else:
		op_obj = obj.json()
	
	if type(obj) == list:
		for key, val in enumerate(obj):
			merge_in(item, val, str(key), nextlabel, iso=iso)
		return
	
	for key in op_obj:
		#from pprint import pprint
		#print("Trying to merge in:", op_obj, key)
		val = op_obj[key]
		merge_in(item, val, key+": ", nextlabel, iso=iso)

def dict_compare(d1, d2):
	d1_keys = set(d1.keys())
	d2_keys = set(d2.keys())
	intersect_keys = d1_keys.intersection(d2_keys)
	added = d1_keys - d2_keys
	removed = d2_keys - d1_keys
	def cmpval(d1, d2, o):
		if isinstance(d1[o], dict) and isinstance(d2[o], dict):
			return dict_same(d1[o], d2[o])
		return d1[o] == d2[o]
	modified = {o : (d1[o], d2[o]) for o in intersect_keys if not(cmpval(d1, d2, o))}
	same = set(o for o in intersect_keys if cmpval(d1,d2,o))
	return added, removed, modified, same

def dict_same(d1, d2):
	added, removed, modified, same = dict_compare(d1, d2)
	#print("added", added, "removed:", removed, "modified:", modified)
	return not(bool(len(added) + len(removed) + len(modified)))


import qrcode
class QQRPainter(qrcode.image.base.BaseImage):
	def __init__(self, border, width, box_size):
		self.border = border
		self.width = width
		self.box_size = box_size
		size = (width + border * 2) * box_size
		self._image = QtGui.QImage(
			size, size, QtGui.QImage.Format_RGB16)
		self._image.fill(QtCore.Qt.white)

	def pixmap(self):
		return QtGui.QPixmap.fromImage(self._image)

	def drawrect(self, row, col):
		painter = QtGui.QPainter(self._image)
		painter.fillRect(
			(col + self.border) * self.box_size,
			(row + self.border) * self.box_size,
			self.box_size, self.box_size,
		QtCore.Qt.black)

	def save(self, stream, kind=None):
		pass

def make_qrcode_image(text):
	bs = 6
	if len(text) >= 60:
		bs = 5
	if len(text) >= 100:
		bs = 4
	return qrcode.make(text, box_size=bs, border=2, image_factory=QQRPainter)


class StackLinker(QtCore.QObject):
	def __init__(self, stack, buttons, pre_highlight, parent=None):
		super(StackLinker, self).__init__(parent)
		self.stack = stack
		self.buttons = [ ]
		self.wr = pre_highlight
		self._index = stack.currentIndex()
		for btn in buttons:
			self.addEntry(*btn)
		self.highlightButtons()
	
	def addEntry(self, btn, qact, tag):
		btn._tag = tag
		btn._index = len(self.buttons)
		self.buttons.append( btn )
		btn.clicked.connect(self.on_button_click)
		
		qact.triggered.connect(self.on_action_trigger)
		qact._index = btn._index
	
	def on_action_trigger(self):
		qact = self.sender()
		self.wr()
		self.setPage(qact._index)
		return False
	
	def on_button_click(self):
		btn = self.sender()
		self.setPage(btn._index)
		return False
	
	def highlightButtons(self):
		for btn in self.buttons:
			if btn._index == self._index:
				btn.setChecked(True)
			else:
				btn.setChecked(False)
	
	def setPageByTag(self, tag):
		i = -1
		for btn in self.buttons:
			i += 1
			if (btn._tag == tag):
				self.setPage(i)
				break
	
	def setPage(self, ind):
		self._index = ind
		self.stack.setCurrentIndex(ind)
		self._index = self.stack.currentIndex()
		self.highlightButtons()
