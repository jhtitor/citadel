from PyQt5.QtWidgets import QCompleter, QPlainTextEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor

class QBrainKeyEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super(QBrainKeyEdit, self).__init__(parent)

        self.completer = BrainCompleter()
        self.completer.setWidget(self)
        self.completer.insertText.connect(self.insertCompletion)

    def insertCompletion(self, completion):
        tc = self.textCursor()
        extra = (len(completion) - len(self.completer.completionPrefix()))
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        if extra > 0:
            tc.insertText(completion[-extra:] + " ")
        else:
            tc.insertText(" ")
        self.setTextCursor(tc)
        self.completer.popup().hide()

    def focusInEvent(self, event):
        if self.completer:
            self.completer.setWidget(self)
        QPlainTextEdit.focusInEvent(self, event)

    def keyPressEvent(self, event):
        # hack -- force uppercase
        if event.text().upper() != event.text().lower():
            from PyQt5.QtGui import QKeyEvent
            event = QKeyEvent(QKeyEvent.KeyPress, event.key(), event.modifiers(), event.text().upper(), False, 1)

        tc = self.textCursor()
        if event.key() == Qt.Key_Return and self.completer.popup().isVisible():
            self.completer.insertText.emit(self.completer.getSelected())
            self.completer.setCompletionMode(QCompleter.PopupCompletion)
            return

        QPlainTextEdit.keyPressEvent(self, event)
        tc.select(QTextCursor.WordUnderCursor)
        cr = self.cursorRect()

        if len(tc.selectedText()) > 0:
            self.completer.setCompletionPrefix(tc.selectedText())
            popup = self.completer.popup()
            popup.setCurrentIndex(self.completer.completionModel().index(0,0))

            cr.setWidth(self.completer.popup().sizeHintForColumn(0) 
            + self.completer.popup().verticalScrollBar().sizeHint().width())
            self.completer.complete(cr)
        else:
            self.completer.popup().hide()

#Completer

from PyQt5.QtWidgets import QCompleter
from PyQt5 import QtCore

from graphenebase.dictionary import words as BrainKeyDictionary

class BrainCompleter(QCompleter):
    insertText = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        words = str.split(BrainKeyDictionary.upper(), ",") #.split(" ")
        QCompleter.__init__(self, words, parent)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.highlighted.connect(self.setHighlighted)

    def setHighlighted(self, text):
        self.lastSelected = text

    def getSelected(self):
        return self.lastSelected
