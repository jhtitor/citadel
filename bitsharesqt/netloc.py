import time
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import Qt

from .work import async
import logging
log = logging.getLogger(__name__)

class NetLoc(object):
	
	def __init__(self):
		pass
	
	def run(self):
		pass


class RemoteFetch(QtCore.QObject):
	def __init__(self, parent=None):
		super(RemoteFetch, self).__init__(parent)
		self.uid = 0
		self.request = None
		
		#global app#
		app = QtGui.QApplication.instance()
		app.aboutToQuit.connect(self.cancel)
		#from work import Request
		#app.aboutToQuit.connect(Request.shutdown) 
	
	def ready_callback(self, uid, result):
		if uid != self.uid:
			return
		log.debug("Data ready from %s: %s" % (uid, result))
	
	def error_callback(self, uid, error):
		if uid != self.uid:
			return
		log.debug("Data error from %s: %s" % (uid, error))
	
	def ping_callback(self, uid, ping_type, ping_data):
		if uid != self.uid:
			return
		log.debug("Unhandled ping %s %s" %(str(ping_type), ping_data))
	
	def cancel(self):
		if self.request is not None:
			self.request.cancelled = True
			self.request = None
		#try:
		#	self.request.cleanup(grabber=self)
		#except:
		#	pass
	
	def fetch(self, method, *args, ready_callback=None, error_callback=None, ping_callback=None, description=""):
		# cancel any pending requests
		self.cancel()
		
		self.uid += 1
		#print("MUST CALL METHOD", method)
		#print("WITH ARGS", args, len(args))
		#print("READY CB:", ready_callback)
		#print("ERROR CB:", error_callback)
		self.request = async(method, args, self.uid,
				ready_callback or self.ready_callback,
				error_callback or self.error_callback,
				ping_callback or self.ping_callback,
				description or "")
	
	def do_fetch(self):
		
		self.fetch(slow_method, "arg1","arg2")
		



if __name__ == "__main__":
    def slow_method(arg1, arg2):
        print( "Starting slow method")
        time.sleep(3)
        return arg1 + arg2

    import sys
    app = QtGui.QApplication(sys.argv)

    obj = RemoteFetch()

    dialog = QtGui.QDialog()
    layout = QtGui.QVBoxLayout(dialog)
    button = QtGui.QPushButton("Generate", dialog)
    progress = QtGui.QProgressBar(dialog)
    progress.setRange(0, 0)
    layout.addWidget(button)
    layout.addWidget(progress)
    button.clicked.connect(obj.do_fetch)
    dialog.show()

    app.exec_()
    app.deleteLater() # avoids some QThread messages in the shell