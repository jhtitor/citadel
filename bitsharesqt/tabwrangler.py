from PyQt5 import QtCore, QtGui

from bitshares.amount import Amount
from bitshares.asset import Asset

from .netloc import RemoteFetch
from .utils import *

import logging
log = logging.getLogger(__name__)

class WindowWithTabWrangler(QtCore.QObject):

	def init_tabwrangler(self, tabwidget):
		self.stash = [ ]

	
	def _allTabs(self):
		tabs = [ ]
		n = len(self.stash)
		for i in range(n):
			yield self.stash[i]
			#tabs.append( tab )
		n = self.ui.tabWidget.count()
		for i in range(n):
			yield self.ui.tabWidget.widget(i)
			#tabs.append( tab )
		#return tabs
	
	def findTab(self, tab_class, tag):
		for tab in self._allTabs():
			if not(isinstance(tab, tab_class)):
				continue
			if not(hasattr(tab, '_tags')):
				continue
			if tag in tab._tags:
				return tab
		return None
	
	def hideTab(self, tab):
		if tab in self.stash:
			return False
		tab._index = i = self.ui.tabWidget.indexOf(tab)
		tab._title = self.ui.tabWidget.tabText(i)
		tab._icon = self.ui.tabWidget.tabIcon(i)
		self.ui.tabWidget.removeTab(i)
		self.stash.append(tab)
		return True
	
	def showTab(self, tab):
		tab_index = self.ui.tabWidget.indexOf
		widget = self.ui.tabWidget
		if tab in self.stash:
			tab = self._removeStashed(tab)
		
		if tab_index(tab) < 0:
			if tab._icon:
				widget.insertTab(tab_index(tab), tab, tab._icon, tab._title)
			else:
				widget.insertTab(tab_index(tab), tab, tab._title)
		self.ui.tabWidget.setCurrentIndex(tab_index(tab))
	
	def setTabVisible(self, tab, on):
		if on:
			return self.showTab(tab)
		else:
			return self.hideTab(tab)
	
	def restoreTab(self, tab_class, tab_creator, ctorarg, tag, to_front=False):
		tab = self.hasTab(tab_class, tag)
		insert = False
		if not tab:
			tab = self.grabStashed(tab_class, tag)
			insert = True
		if not tab:
			tab = tab_creator(ctorarg, tag)
			insert = True
		if insert:
			if tab._icon:
				self.ui.tabWidget.insertTab(tab._index, tab, tab._icon, tab._title)
			else:
				self.ui.tabWidget.insertTab(tab._index, tab, tab._title)
		if to_front:
			cur_index = self.ui.tabWidget.indexOf(tab)
			self.ui.tabWidget.setCurrentIndex(cur_index)
	
	def _removeStashed(self, tab):
		n = len(self.stash)
		for i in range(n):
			_tab = self.stash[i]
			if _tab == tab:
				del self.stash[i]
				return _tab
		return None
	
	def grabStashed(self, check_class, tag):
		n = len(self.stash)
		for i in range(n):
			tab = self.stash[i]
			if isinstance(tab, check_class):
				if (tag in tab._tags):
					del self.stash[i]
					return tab
		return None
	
	def hasTab(self, check_class, tag):
		n = self.ui.tabWidget.count()
		for i in range(n):
			tab = self.ui.tabWidget.widget(i)
			if isinstance(tab, check_class):
				if (tag in tab._tags):
					return tab
		return False
		
	
	def tagToFront(self, tag, check_class=QtGui.QWidget):
		tab = self.findTab(check_class, tag)
		if not tab:
			return
		self.showTab(tab)
		index = self.ui.tabWidget.indexOf(tab)
		self.ui.tabWidget.setCurrentIndex(index)
	
	def destroyTab(self, check_class, tag):
		tab = self.hasTab(check_class, tag)
		remove = True
		if not tab:
			remove = False
			tab = self.grabStashed(check_class, tag)
		if not tab:
			return
		if remove:
			i = self.ui.tabWidget.indexOf(tab)
			self.ui.tabWidget.removeTab(i)
		try:
			tab.close()
		except:
			pass
		tab = None
