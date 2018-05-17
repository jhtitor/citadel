# Running (on Linux)

To install the dependecies and vendor-drop some additional code,
run:

```
pip3 install -r requirements.txt
python3 vendor_package.py
```

To run the program, execute `./citadel`.

# Windows

## Windows XP 32-bit

Use latest version of python 3.4
https://www.python.org/ftp/python/3.4.4/python-3.4.4.msi

Also install latest version of pywin for python 3.4
https://github.com/mhammond/pywin32/releases/download/b221/pywin32-221.win32-py3.4.exe

PyQt4 wheel distribution, get it from
https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyqt4
You need the `PyQt4-4.11.4-cp34-cp34m-win32.whl` one

<s>
PyCrypto
http://www.voidspace.org.uk/python/pycrypto-2.6.1/pycrypto-2.6.1-cp34-none-win32.whl
</s>
PyCryptodome
```
python -m pip install pycryptodome
```

Note, pycryptodomex will also be pulled from requirements.txt.
But the vanilla pycryptodome MUST be installed explicitly by you.

<s>
secp256k1prp-py
https://github.com/jhtitor/secp256k1prp-py/releases/download/0.13.2.5prp/secp256k1prp-0.13.2-cp34-cp34m-win32.whl
</s>

```
python -m pip install scrypt
```

OpenSSL .dlls (for scrypt), unpack into source folder
https://indy.fulgan.com/SSL/openssl-1.0.2o-i386-win32.zip

Prepare everything else:
```
python -m pip -r requirements.txt
python vendor_package.py
```

You can now run
```
build.bat
```

## Windows 7+ 64-bit

Note: building with python 3.6 is trickier (than, say, 3.5), but
is possible.

PyQt4 wheel distribution, get it from
https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyqt4
You need the `PyQt4-4.11.4-cp36-cp36m-win_amd64.whl` one

```
python -m pip install scrypt
```

OpenSSL .dlls (for scrypt), unpack into source folder
https://indy.fulgan.com/SSL/openssl-1.0.2o-i386-win32.zip

```
py -3.6 -m pip install -r requirements.txt
py -3.6 venor_package.py
```

# OSX

Install Command-Line Developer tools
```
gcc -v
```

## MacPorts

```
sudo port install py35-pyqt4 py35-pip
```


```
pip-3.5 install -r requirements.txt --user
python3 vendor_package.py
```


Bundle
```
make App
```
