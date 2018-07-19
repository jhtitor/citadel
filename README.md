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

PyQt5 5.5.1 (latest version for python 3.4)
https://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-5.5.1/PyQt5-5.5.1-gpl-Py3.4-Qt5.5.1-x32.exe/download

PyCryptodome
```
python -m pip install pycryptodome
```

Note, pycryptodomex will also be pulled from requirements.txt.
But the vanilla pycryptodome MUST be installed explicitly by you.

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

PyQt5 from pip will work just fine.
```
py -3.6 -m pip install PyQt5
```

OpenSSL .dlls (for scrypt), unpack into source folder
https://indy.fulgan.com/SSL/openssl-1.0.2o-x64_86-win64.zip

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
sudo port install py35-pyqt5 py35-pip
```


```
pip-3.5 install -r requirements.txt --user
python3 vendor_package.py
```


Bundle
```
make app
```

To create dmgs, get dmgbuild
```
pip-3.5 install pyinstaller dmgbuild --install-option="--prefix=/opt/local/bin" --user
```

```
make dmg
```