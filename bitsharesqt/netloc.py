import time
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt

from .work import async
import logging
log = logging.getLogger(__name__)

class Cancelled(Exception):
	pass

class NetLoc(object):
	
	def __init__(self):
		pass
	
	def run(self):
		pass

def num_args(method):
	num_args = method.__code__.co_argcount
	num_kwargs = len(method.__defaults__) if method.__defaults__ else 0
	return num_args - num_kwargs

class RemoteFetch(QtCore.QObject):
	def __init__(self, parent=None):
		super(RemoteFetch, self).__init__(parent)
		self.uid = 0
		self.request = None
		self.cb_ready = None
		self.cb_error = None
		self.cb_ping = None
		
		#global app#
		app = QtGui.QApplication.instance()
		app.aboutToQuit.connect(self.cancel)
		#from work import Request
		#app.aboutToQuit.connect(Request.shutdown)
	
	def ready_callback(self, uid, result):
		if uid != self.uid:
			return
		if self.cb_ready:
			self.cb_ready(uid, result)
		else:
			log.debug("Unhandled data ready from %s: %s", str(uid), str(result))
	
	def error_callback(self, uid, error):
		if uid != self.uid:
			return
		if self.cb_error:
			self.cb_error(uid, error)
		else:
			log.debug("Unhandled data error from %s: %s", str(uid), str(error))
	
	def ping_callback(self, uid, ping_type, ping_data):
		if uid != self.uid:
			return
		if self.cb_ping:
			args = [ uid, ping_type, ping_data ]
			num = num_args(self.cb_ping)-1
			if num < len(args):
				args = args[0:num]
			self.cb_ping(*args)
		else:
			log.debug("Unhandled ping %s %s", str(ping_type), str(ping_data))
	
	def cancel(self):
		if self.request is not None:
			self.request.cancelled = True
			self.request = None
		#try:
		#	self.request.cleanup(grabber=self)
		#except:
		#	pass
		self.cb_ready = None
		self.cb_error = None
		self.cb_ping = None
	
	def fetch(self, method, *args, ready_callback=None, error_callback=None, ping_callback=None, description=""):
		# cancel any pending requests
		self.cancel()
		
		self.uid += 1
		self.cb_ready = ready_callback
		self.cb_error = error_callback
		self.cb_ping = ping_callback
		#print("MUST CALL METHOD", method)
		#print("WITH ARGS", args, len(args))
		#print("READY CB:", ready_callback)
		#print("ERROR CB:", error_callback)
		self.request = async(method, args, self.uid,
				self.ready_callback,
				self.error_callback,
				self.ping_callback,
				description or "")
	



if __name__ == "__main__":
    def slow_method(arg1, arg2, request_handler=None):
        rh = request_handler # short alias
        print("Starting slow method")
        for i in range(0, 100):
            if rh:
                rh.ping(i, None)
            time.sleep(0.01)
        return arg1 + arg2

    from PyQt5 import QtWidgets as QtGui
    import sys
    app = QtGui.QApplication(sys.argv)

    obj = RemoteFetch()

    dialog = QtGui.QDialog()
    layout = QtGui.QVBoxLayout(dialog)
    button = QtGui.QPushButton("Generate", dialog)
    progress = QtGui.QProgressBar(dialog)
    progress.setRange(0, 100)
    progress.setValue(0)
    layout.addWidget(button)
    layout.addWidget(progress)

    def on_click():
        obj.fetch(slow_method, "arg1","arg2", ping_callback=on_ping)

    def on_ping(uid=None, ct=None, cd=None):
        progress.setValue(ct)

    button.clicked.connect(on_click)
    dialog.show()

    app.exec_()
    app.deleteLater() # avoids some QThread messages in the shell